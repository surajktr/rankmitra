from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
CORS(app)

PORT = 3001

# Full Exam Configurations matching index.ts
EXAM_CONFIGS = {
    'SSC_CGL_PRE': {
        'id': 'SSC_CGL_PRE',
        'name': 'SSC CGL PRE (Tier-I)',
        'displayName': 'SSC CGL Tier-I',
        'emoji': '🟢',
        'subjects': [
            {'name': 'General Intelligence & Reasoning', 'part': 'A', 'totalQuestions': 25, 'maxMarks': 50, 'correctMarks': 2, 'negativeMarks': 0.50},
            {'name': 'General Awareness', 'part': 'B', 'totalQuestions': 25, 'maxMarks': 50, 'correctMarks': 2, 'negativeMarks': 0.50},
            {'name': 'Quantitative Aptitude', 'part': 'C', 'totalQuestions': 25, 'maxMarks': 50, 'correctMarks': 2, 'negativeMarks': 0.50},
            {'name': 'English Comprehension', 'part': 'D', 'totalQuestions': 25, 'maxMarks': 50, 'correctMarks': 2, 'negativeMarks': 0.50},
        ],
        'totalQuestions': 100,
        'maxMarks': 200,
    },
    'DELHI_POLICE_HEAD_CONSTABLE': {
        'id': 'DELHI_POLICE_HEAD_CONSTABLE',
        'name': 'Delhi Police Head Constable (CBT)',
        'displayName': 'DP Head Constable',
        'emoji': '🚔',
        'subjects': [
            {'name': 'General Awareness', 'part': 'A', 'totalQuestions': 25, 'maxMarks': 25, 'correctMarks': 1, 'negativeMarks': 0.25},
            {'name': 'Quantitative Aptitude', 'part': 'B', 'totalQuestions': 20, 'maxMarks': 20, 'correctMarks': 1, 'negativeMarks': 0.25},
            {'name': 'Reasoning', 'part': 'C', 'totalQuestions': 25, 'maxMarks': 25, 'correctMarks': 1, 'negativeMarks': 0.25},
            {'name': 'English Language', 'part': 'D', 'totalQuestions': 20, 'maxMarks': 20, 'correctMarks': 1, 'negativeMarks': 0.25},
            {'name': 'Computer Fundamentals', 'part': 'E', 'totalQuestions': 10, 'maxMarks': 10, 'correctMarks': 1, 'negativeMarks': 0.25},
        ],
        'totalQuestions': 100,
        'maxMarks': 100,
    },
}

def generate_part_urls(input_url, exam_config):
    """Generate URLs for all parts based on exam config (matching index.ts generatePartUrls)"""
    parts = []
    
    url_parts = input_url.split('?')
    query_string = url_parts[1] if len(url_parts) > 1 else ''
    base_path = url_parts[0]
    last_slash = base_path.rfind('/')
    base_dir = base_path[:last_slash + 1]
    
    # Map parts to file names (matching index.ts)
    part_file_map = {
        'A': 'ViewCandResponse.aspx',
        'B': 'ViewCandResponse2.aspx',
        'C': 'ViewCandResponse3.aspx',
        'D': 'ViewCandResponse4.aspx',
        'E': 'ViewCandResponse5.aspx',
    }
    
    for subject in exam_config['subjects']:
        part = subject['part']
        file_name = part_file_map.get(part)
        if file_name:
            url = f"{base_dir}{file_name}"
            if query_string:
                url += f"?{query_string}"
            parts.append({'part': part, 'url': url, 'subject': subject})
    
    return parts

def parse_candidate_info(html):
    """Parse candidate information from HTML (matching index.ts parseCandidateInfo)"""
    def get_table_value(label):
        pattern = rf'<td[^>]*>[^<]*{re.escape(label)}[^<]*</td>\s*<td[^>]*>:?(?:&nbsp;)*\s*([^<]+)'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).replace('&nbsp;', ' ').strip()
        return ''
    
    return {
        'rollNumber': get_table_value('Roll No') or get_table_value('Roll Number') or '',
        'name': get_table_value('Candidate Name') or get_table_value('Name') or '',
        'examLevel': get_table_value('Exam Level') or '',
        'testDate': get_table_value('Test Date') or '',
        'shift': get_table_value('Test Time') or get_table_value('Shift') or '',
        'centreName': get_table_value('Centre Name') or get_table_value('Center Name') or '',
    }

def get_language_urls(image_url):
    """Get Hindi and English URLs (matching index.ts getLanguageUrls)"""
    if not image_url:
        return {'hindi': '', 'english': ''}
    
    is_hindi = bool(re.search(r'_HI\.(jpg|jpeg|png|gif)', image_url, re.IGNORECASE))
    is_english = bool(re.search(r'_EN\.(jpg|jpeg|png|gif)', image_url, re.IGNORECASE))
    
    hindi_url = image_url
    english_url = image_url
    
    if is_hindi:
        english_url = re.sub(r'_HI\.(jpg|jpeg|png|gif)', r'_EN.\1', image_url, flags=re.IGNORECASE)
    elif is_english:
        hindi_url = re.sub(r'_EN\.(jpg|jpeg|png|gif)', r'_HI.\1', image_url, flags=re.IGNORECASE)
    
    return {'hindi': hindi_url, 'english': english_url}

def parse_questions_for_part(html, part, base_url, subject, question_offset):
    """Parse questions from HTML for a specific part (matching index.ts parseQuestionsForPart)"""
    print(f'=== PARSER VERSION 2.0 - Multi-image extraction enabled - Part {part} ===')
    questions = []
    
    url_parts = base_url.split('?')[0]
    last_slash = url_parts.rfind('/')
    base_dir = url_parts[:last_slash + 1]
    
    # Find all question tables
    question_table_pattern = re.compile(r'<table[^>]*>[\s\S]*?Q\.No:\s*&nbsp;(\d+)[\s\S]*?</table>', re.IGNORECASE)
    
    for table_match in question_table_pattern.finditer(html):
        q_num = int(table_match.group(1))
        table_content = table_match.group(0)
        
        # Extract question image
        q_img_pattern = re.search(r'Q\.No:\s*&nbsp;\d+</font></td><td[^>]*>[\s\S]*?<img[^>]+src\s*=\s*["\']([^"\']+)["\']', table_content, re.IGNORECASE)
        question_image_url = q_img_pattern.group(1) if q_img_pattern else ''
        
        if question_image_url and not question_image_url.startswith('http'):
            question_image_url = base_dir + question_image_url
        
        # Get language URLs for question
        question_lang_urls = get_language_urls(question_image_url)
        final_q_hindi = question_lang_urls['hindi'] or question_image_url
        final_q_english = question_lang_urls['english'] or question_image_url
        
        options = []
        option_ids = ['A', 'B', 'C', 'D']
        
        # Parse option rows
        option_row_pattern = re.compile(r'<tr[^>]*(?:bgcolor\s*=\s*["\']([^"\']+)["\'])?[^>]*>([\s\S]*?)</tr>', re.IGNORECASE)
        opt_idx = 0
        found_question_row = False
        
        for row_match in option_row_pattern.finditer(table_content):
            if opt_idx >= 4:
                break
                
            row_bgcolor = (row_match.group(1) or '').lower()
            row_content = row_match.group(2)
            
            if 'Q.No:' in row_content:
                found_question_row = True
                continue
            
            if not found_question_row:
                continue
            
            # Extract ALL images from this option row
            img_regex = re.compile(r'<img[^>]+src\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
            image_urls = []
            
            for img_match in img_regex.finditer(row_content):
                url = img_match.group(1)
                if url and not url.startswith('http'):
                    url = base_dir + url
                image_urls.append(url)
            
            if not image_urls:
                continue
            
            # Identify Hindi and English URLs
            hindi_url = ''
            english_url = ''
            default_url = image_urls[0]
            
            for url in image_urls:
                if re.search(r'_HI\.(jpg|jpeg|png|gif)', url, re.IGNORECASE):
                    hindi_url = url
                elif re.search(r'_EN\.(jpg|jpeg|png|gif)', url, re.IGNORECASE):
                    english_url = url
            
            # Fallback logic
            if not hindi_url and not english_url:
                lang_urls = get_language_urls(default_url)
                hindi_url = lang_urls['hindi'] or default_url
                english_url = lang_urls['english'] or default_url
            else:
                if not hindi_url:
                    hindi_url = english_url or default_url
                if not english_url:
                    english_url = hindi_url or default_url
            
            # Get bgcolor from td if not on tr
            bgcolor = row_bgcolor
            if not bgcolor:
                td_bg_match = re.search(r'bgcolor\s*=\s*["\']([^"\']+)["\']', row_content, re.IGNORECASE)
                if td_bg_match:
                    bgcolor = td_bg_match.group(1).lower()
            
            is_green = 'green' in bgcolor
            is_red = 'red' in bgcolor
            is_yellow = 'yellow' in bgcolor
            
            is_correct = is_green or is_yellow
            is_selected = is_green or is_red
            
            options.append({
                'id': option_ids[opt_idx],
                'imageUrl': default_url,
                'imageUrlHindi': hindi_url,
                'imageUrlEnglish': english_url,
                'isSelected': is_selected,
                'isCorrect': is_correct,
            })
            
            opt_idx += 1
        
        # Pad options to 4
        while len(options) < 4:
            options.append({
                'id': option_ids[len(options)],
                'imageUrl': '',
                'imageUrlHindi': '',
                'imageUrlEnglish': '',
                'isSelected': False,
                'isCorrect': False,
            })
        
        if len(options) >= 2:
            # Determine status
            has_selected = any(o['isSelected'] for o in options)
            selected_is_correct = any(o['isSelected'] and o['isCorrect'] for o in options)
            
            if not has_selected:
                status = 'unattempted'
            elif selected_is_correct:
                status = 'correct'
            else:
                status = 'wrong'
            
            # Calculate marks
            if status == 'correct':
                marks_awarded = subject['correctMarks']
            elif status == 'wrong':
                marks_awarded = -subject['negativeMarks']
            else:
                marks_awarded = 0
            
            actual_question_number = question_offset + q_num
            
            questions.append({
                'questionNumber': actual_question_number,
                'part': part,
                'subject': subject['name'],
                'questionImageUrl': question_image_url,
                'questionImageUrlHindi': final_q_hindi,
                'questionImageUrlEnglish': final_q_english,
                'options': options,
                'status': status,
                'marksAwarded': marks_awarded,
            })
    
    return questions

def calculate_sections(questions, exam_config):
    """Calculate section-wise breakdown (matching index.ts calculateSections)"""
    sections = []
    
    for subject in exam_config['subjects']:
        part_questions = [q for q in questions if q['part'] == subject['part']]
        correct = len([q for q in part_questions if q['status'] == 'correct'])
        wrong = len([q for q in part_questions if q['status'] == 'wrong'])
        unattempted = len([q for q in part_questions if q['status'] == 'unattempted'])
        score = correct * subject['correctMarks'] - wrong * subject['negativeMarks']
        
        sections.append({
            'part': subject['part'],
            'subject': subject['name'],
            'correct': correct,
            'wrong': wrong,
            'unattempted': unattempted,
            'score': score,
            'maxMarks': subject['maxMarks'],
            'correctMarks': subject['correctMarks'],
            'negativeMarks': subject['negativeMarks'],
            'isQualifying': subject.get('isQualifying', False),
        })
    
    return sections

@app.route('/', methods=['POST'])
def analyze():
    try:
        data = request.json
        url = data.get('url')
        exam_type = data.get('examType', 'DELHI_POLICE_HEAD_CONSTABLE')
        language = data.get('language', 'hindi')
        
        print(f'Analyzing URL: {url} | Exam: {exam_type} | Language: {language}')
        
        # Get exam config
        exam_config = EXAM_CONFIGS.get(exam_type, EXAM_CONFIGS['DELHI_POLICE_HEAD_CONSTABLE'])
        
        # Generate URLs for all parts
        part_urls = generate_part_urls(url, exam_config)
        print(f'Fetching parts: {[p["part"] for p in part_urls]}')
        
        all_questions = []
        candidate = None
        
        # Calculate question offsets
        question_offset = 0
        part_offsets = {}
        for subject in exam_config['subjects']:
            part_offsets[subject['part']] = question_offset
            question_offset += subject['totalQuestions']
        
        # Fetch and parse all parts
        for part_info in part_urls:
            part = part_info['part']
            part_url = part_info['url']
            subject = part_info['subject']
            
            print(f'Scraping Part {part}: {part_url}')
            
            try:
                response = requests.get(part_url, timeout=30)
                html = response.text
                
                # Parse candidate info from first part
                if not candidate:
                    candidate = parse_candidate_info(html)
                
                # Parse questions
                questions = parse_questions_for_part(html, part, part_url, subject, part_offsets[part])
                all_questions.extend(questions)
                print(f'Part {part} parsed: {len(questions)} questions')
                
            except Exception as e:
                print(f'Error scraping Part {part}: {str(e)}')
                continue
        
        # Sort questions by number
        all_questions.sort(key=lambda q: q['questionNumber'])
        
        # Use default candidate if parsing failed
        if not candidate or not candidate.get('rollNumber'):
            candidate = {
                'rollNumber': '',
                'name': '',
                'examLevel': exam_config['name'],
                'testDate': '',
                'shift': '',
                'centreName': '',
            }
        
        # Calculate sections
        sections = calculate_sections(all_questions, exam_config)
        
        # Calculate totals
        correct_count = len([q for q in all_questions if q['status'] == 'correct'])
        wrong_count = len([q for q in all_questions if q['status'] == 'wrong'])
        unattempted_count = len([q for q in all_questions if q['status'] == 'unattempted'])
        total_score = sum(s['score'] for s in sections)
        
        result = {
            'candidate': candidate,
            'examType': exam_type,
            'examConfig': exam_config,
            'language': language,
            'totalScore': total_score,
            'maxScore': exam_config['maxMarks'],
            'totalQuestions': len(all_questions),
            'correctCount': correct_count,
            'wrongCount': wrong_count,
            'unattemptedCount': unattempted_count,
            'sections': sections,
            'questions': all_questions,
        }
        
        print(f'Analysis complete. Total score: {total_score}/{exam_config["maxMarks"]}')
        
        return jsonify({'success': True, 'data': result})
        
    except Exception as e:
        print(f'Error: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print(f'Starting Python Crawler Server on port {PORT}...')
    print('This server fetches all parts (A, B, C, D, E) and calculates section-wise scores')
    app.run(port=PORT, debug=True)


# Exam Configurations (Simplified for local testing)
EXAM_CONFIGS = {
    'DELHI_POLICE_HEAD_CONSTABLE': {
        'id': 'DELHI_POLICE_HEAD_CONSTABLE',
        'subjects': [
             {'name': 'General Awareness', 'part': 'A', 'totalQuestions': 25, 'maxMarks': 25, 'correctMarks': 1, 'negativeMarks': 0.25},
             {'name': 'Quantitative Aptitude', 'part': 'B', 'totalQuestions': 20, 'maxMarks': 20, 'correctMarks': 1, 'negativeMarks': 0.25},
             {'name': 'Reasoning', 'part': 'C', 'totalQuestions': 25, 'maxMarks': 25, 'correctMarks': 1, 'negativeMarks': 0.25},
             {'name': 'English Language', 'part': 'D', 'totalQuestions': 20, 'maxMarks': 20, 'correctMarks': 1, 'negativeMarks': 0.25},
             {'name': 'Computer Fundamentals', 'part': 'E', 'totalQuestions': 10, 'maxMarks': 10, 'correctMarks': 1, 'negativeMarks': 0.25},
        ],
        'maxMarks': 100
    }
    # Add other configs as needed, or default to generic if unknown
}

def get_language_urls(image_url):
    if not image_url:
        return {'hindi': '', 'english': ''}
    
    is_hindi = '_HI.' in image_url
    is_english = '_EN.' in image_url
    
    hindi_url = image_url
    english_url = image_url
    
    if is_hindi:
        english_url = image_url.replace('_HI.', '_EN.')
    elif is_english:
        hindi_url = image_url.replace('_EN.', '_HI.')
        
    return {'hindi': hindi_url, 'english': english_url}

def parse_questions(html, part, base_dir, subject, question_offset):
    questions = []
    
    # Python regex for finding tables with Q.No
    # Note: Regex parsing HTML is fragile, but matches the TS implementation structure
    table_pattern = re.compile(r'<table[^>]*>[\s\S]*?Q\.No:\s*&nbsp;(\d+)[\s\S]*?<\/table>', re.IGNORECASE)
    
    for match in table_pattern.finditer(html):
        table_content = match.group(0)
        q_num = int(match.group(1))
        
        # Extract Question Image
        q_img_pattern = re.search(r'Q\.No:\s*&nbsp;\d+<\/font><\/td><td[^>]*>[\s\S]*?<img[^>]+src\s*=\s*["\']([^"\']+)["\']', table_content, re.IGNORECASE)
        question_image_url = q_img_pattern.group(1) if q_img_pattern else ''
        
        if question_image_url and not question_image_url.startswith('http'):
            question_image_url = base_dir + question_image_url
            
        # Get Language URLs for question (Questions usually share UUIDs)
        q_lang_urls = get_language_urls(question_image_url)
        final_q_hindi = q_lang_urls['hindi']
        final_q_english = q_lang_urls['english']
        
        options = []
        option_ids = ['A', 'B', 'C', 'D']
        
        # Extract Options
        # Find all rows that might contain options
        row_iter = re.finditer(r'<tr[^>]*(?:bgcolor\s*=\s*["\']([^"\']+)["\'])?[^>]*>([\s\S]*?)<\/tr>', table_content, re.IGNORECASE)
        
        opt_idx = 0
        found_question_row = False
        
        for row_match in row_iter:
            if opt_idx >= 4: break
            
            row_bgcolor = (row_match.group(1) or '').lower()
            row_content = row_match.group(2)
            
            if 'Q.No:' in row_content:
                found_question_row = True
                continue
            
            if not found_question_row:
                continue
                
            # Extract ALL images from this option row (Robust Fix)
            img_regex = re.compile(r'<img[^>]+src\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
            image_urls = []
            
            for img_m in img_regex.finditer(row_content):
                url = img_m.group(1)
                if url and not url.startswith('http'):
                    url = base_dir + url
                image_urls.append(url)
            
            if not image_urls:
                continue
                
            # Identify Hindi vs English based on suffix
            hindi_url = ''
            english_url = ''
            default_url = image_urls[0]
            
            for url in image_urls:
                if '_HI.' in url:
                    hindi_url = url
                elif '_EN.' in url:
                    english_url = url
            
            # Fallback Logic
            if not hindi_url and not english_url:
                lang_urls = get_language_urls(default_url)
                hindi_url = lang_urls['hindi']
                english_url = lang_urls['english']
            else:
                if not hindi_url: hindi_url = english_url or default_url
                if not english_url: english_url = hindi_url or default_url

            # Determine Correctness
            if not row_bgcolor:
               bg_match = re.search(r'bgcolor\s*=\s*["\']([^"\']+)["\']', row_content, re.IGNORECASE)
               if bg_match:
                   row_bgcolor = bg_match.group(1).lower()
            
            is_green = 'green' in row_bgcolor
            is_red = 'red' in row_bgcolor
            is_yellow = 'yellow' in row_bgcolor
            
            is_correct = is_green or is_yellow
            is_selected = is_green or is_red
            
            options.append({
                'id': option_ids[opt_idx],
                'imageUrl': default_url,
                'imageUrlHindi': hindi_url,
                'imageUrlEnglish': english_url,
                'isSelected': is_selected,
                'isCorrect': is_correct
            })
            
            opt_idx += 1
            
        # Pad options if less than 4
        while len(options) < 4:
            options.append({
                'id': option_ids[len(options)],
                'imageUrl': '',
                'imageUrlHindi': '',
                'imageUrlEnglish': '',
                'isSelected': False,
                'isCorrect': False
            })
            
        # Determine Status
        status = 'unattempted'
        has_selected = any(o['isSelected'] for o in options)
        selected_is_correct = any(o['isSelected'] and o['isCorrect'] for o in options)
        
        if not has_selected:
            status = 'unattempted'
        elif selected_is_correct:
            status = 'correct'
        else:
            status = 'wrong'
            
        # Calculate Marks
        marks = 0
        if status == 'correct': marks = subject['correctMarks']
        elif status == 'wrong': marks = -subject['negativeMarks']
        
        questions.append({
            'questionNumber': question_offset + q_num,
            'part': part,
            'subject': subject['name'],
            'questionImageUrl': question_image_url,
            'questionImageUrlHindi': final_q_hindi,
            'questionImageUrlEnglish': final_q_english,
            'options': options,
            'status': status,
            'marksAwarded': marks
        })
        
    return questions

@app.route('/', methods=['POST'])
def analyze():
    try:
        data = request.json
        url = data.get('url')
        exam_type = data.get('examType', 'DELHI_POLICE_HEAD_CONSTABLE') # Default if missing
        language = data.get('language', 'hindi')
        
        print(f"Analyzing URL: {url} | Exam: {exam_type} | Lang: {language}")
        
        # Fetch Content
        response = requests.get(url)
        html_content = response.text
        
        # Base Directory for relative URLs
        base_dir = url.split('?')[0].rsplit('/', 1)[0] + '/'
        
        # Config
        config = EXAM_CONFIGS.get(exam_type, EXAM_CONFIGS['DELHI_POLICE_HEAD_CONSTABLE'])
        
        all_questions = []
        # Simplified: Just parsing the first subject/part found in the single URL
        # Real logic might need to fetch multiple pages if configured, but start simple
        subject = config['subjects'][0] # Taking first subject as default container
        
        # In a real scenario, you'd iterate subjects and fetch their specific pages if needed
        # For simplicity, we parse the provided page assuming it contains questions
        # Note: The original logic handled multiple parts. For this Python script, 
        # we will parse everything from the single page provided.
        
        parsed_questions = parse_questions(html_content, subject['part'], base_dir, subject, 0)
        
        result = {
            'candidate': {}, # Placeholder
            'examType': exam_type,
            'examConfig': config,
            'language': language,
            'totalScore': sum(q['marksAwarded'] for q in parsed_questions),
            'maxScore': config['maxMarks'],
            'totalQuestions': len(parsed_questions),
            'correctCount': len([q for q in parsed_questions if q['status'] == 'correct']),
            'wrongCount': len([q for q in parsed_questions if q['status'] == 'wrong']),
            'unattemptedCount': len([q for q in parsed_questions if q['status'] == 'unattempted']),
            'sections': [],
            'questions': parsed_questions
        }
        
        return jsonify({'success': True, 'data': result})

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print(f"Starting Python Crawler Server on port {PORT}...")
    app.run(port=PORT, debug=True)
