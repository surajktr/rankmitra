// Local development server for testing the analyze function
// Run with: node local-server.js

import http from 'http';

const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Content-Type': 'application/json'
};

// Helper function to get both Hindi and English image URLs
const getLanguageUrls = (imageUrl) => {
    if (!imageUrl) return {};

    const isHindi = /_HI\.(jpg|jpeg|png|gif)/i.test(imageUrl);
    const isEnglish = /_EN\.(jpg|jpeg|png|gif)/i.test(imageUrl);

    let hindiUrl = imageUrl;
    let englishUrl = imageUrl;

    if (isHindi) {
        englishUrl = imageUrl.replace(/_HI\.(jpg)/i, '_EN.$1')
            .replace(/_HI\.(jpeg)/i, '_EN.$1')
            .replace(/_HI\.(png)/i, '_EN.$1')
            .replace(/_HI\.(gif)/i, '_EN.$1');
    } else if (isEnglish) {
        hindiUrl = imageUrl.replace(/_EN\.(jpg)/i, '_HI.$1')
            .replace(/_EN\.(jpeg)/i, '_HI.$1')
            .replace(/_EN\.(png)/i, '_HI.$1')
            .replace(/_EN\.(gif)/i, '_HI.$1');
    }

    return { hindi: hindiUrl, english: englishUrl };
};

// Parse questions from HTML
function parseQuestionsForPart(html, part, baseUrl, subject, questionOffset) {
    console.log('=== PARSER VERSION 2.0 - Multi-image extraction enabled ===');
    const questions = [];

    const urlParts = baseUrl.split('?')[0];
    const lastSlashIndex = urlParts.lastIndexOf('/');
    const baseDir = urlParts.substring(0, lastSlashIndex + 1);

    const questionTablePattern = /<table[^>]*>[\s\S]*?Q\.No:\s*&nbsp;(\d+)[\s\S]*?<\/table>/gi;
    let tableMatch;

    while ((tableMatch = questionTablePattern.exec(html)) !== null) {
        const qNum = parseInt(tableMatch[1]);
        const tableContent = tableMatch[0];

        const qImgPattern = /Q\.No:\s*&nbsp;\d+<\/font><\/td><td[^>]*>[\s\S]*?<img[^>]+src\s*=\s*["']([^"']+)["']/i;
        const qImgMatch = tableContent.match(qImgPattern);
        let questionImageUrl = qImgMatch ? qImgMatch[1] : '';

        if (questionImageUrl && !questionImageUrl.startsWith('http')) {
            questionImageUrl = baseDir + questionImageUrl;
        }

        const questionLangUrls = getLanguageUrls(questionImageUrl);
        const finalQuestionHindiUrl = questionLangUrls.hindi || questionImageUrl;
        const finalQuestionEnglishUrl = questionLangUrls.english || questionImageUrl;

        const options = [];
        const optionIds = ['A', 'B', 'C', 'D'];

        const optionRowPattern = /<tr[^>]*(?:bgcolor\s*=\s*["']([^"']+)["'])?[^>]*>([\s\S]*?)<\/tr>/gi;
        let optionMatch;
        let optIdx = 0;
        let foundQuestionRow = false;

        while ((optionMatch = optionRowPattern.exec(tableContent)) !== null && optIdx < 4) {
            const rowBgcolor = (optionMatch[1] || '').toLowerCase();
            const rowContent = optionMatch[2];

            if (rowContent.includes('Q.No:')) {
                foundQuestionRow = true;
                continue;
            }

            if (!foundQuestionRow) continue;

            // Extract ALL images from this option row
            const imgRegex = /<img[^>]+src\s*=\s*["']([^"']+)["']/gi;
            const imageUrls = [];
            let match;

            while ((match = imgRegex.exec(rowContent)) !== null) {
                let imgUrl = match[1];
                if (imgUrl && !imgUrl.startsWith('http')) {
                    imgUrl = baseDir + imgUrl;
                }
                imageUrls.push(imgUrl);
            }

            console.log(`Part ${part}, Q${qNum}, Row ${optIdx}: Found ${imageUrls.length} images:`, imageUrls);

            if (imageUrls.length === 0) continue;

            // Determine which image is Hindi and which is English
            let hindiUrl = '';
            let englishUrl = '';
            let defaultUrl = imageUrls[0];

            for (const url of imageUrls) {
                if (/_HI\.(jpg|jpeg|png|gif)/i.test(url)) {
                    hindiUrl = url;
                } else if (/_EN\.(jpg|jpeg|png|gif)/i.test(url)) {
                    englishUrl = url;
                }
            }

            if (!hindiUrl && !englishUrl) {
                const langUrls = getLanguageUrls(defaultUrl);
                hindiUrl = langUrls.hindi || defaultUrl;
                englishUrl = langUrls.english || defaultUrl;
            } else {
                if (!hindiUrl) hindiUrl = englishUrl || defaultUrl;
                if (!englishUrl) englishUrl = hindiUrl || defaultUrl;
            }

            let bgcolor = rowBgcolor;
            if (!bgcolor) {
                const tdBgMatch = rowContent.match(/bgcolor\s*=\s*["']([^"']+)["']/i);
                if (tdBgMatch) {
                    bgcolor = tdBgMatch[1].toLowerCase();
                }
            }

            const isGreen = bgcolor.includes('green');
            const isRed = bgcolor.includes('red');
            const isYellow = bgcolor.includes('yellow');

            const isCorrect = isGreen || isYellow;
            const isSelected = isGreen || isRed;

            console.log(`Part ${part}, Q${qNum}, Option ${optionIds[optIdx]}:`, {
                hindiUrl: hindiUrl,
                englishUrl: englishUrl
            });

            options.push({
                id: optionIds[optIdx],
                imageUrl: defaultUrl,
                imageUrlHindi: hindiUrl,
                imageUrlEnglish: englishUrl,
                isSelected,
                isCorrect,
            });

            optIdx++;
        }

        if (options.length >= 2) {
            while (options.length < 4) {
                options.push({
                    id: optionIds[options.length],
                    imageUrl: '',
                    imageUrlHindi: '',
                    imageUrlEnglish: '',
                    isSelected: false,
                    isCorrect: false,
                });
            }

            let status = 'unattempted';
            const hasSelected = options.some(o => o.isSelected);
            const selectedIsCorrect = options.some(o => o.isSelected && o.isCorrect);

            if (!hasSelected) {
                status = 'unattempted';
            } else if (selectedIsCorrect) {
                status = 'correct';
            } else {
                status = 'wrong';
            }

            const marksAwarded = status === 'correct'
                ? subject.correctMarks
                : status === 'wrong'
                    ? -subject.negativeMarks
                    : 0;

            const actualQuestionNumber = questionOffset + qNum;

            questions.push({
                questionNumber: actualQuestionNumber,
                part,
                subject: subject.name,
                questionImageUrl,
                questionImageUrlHindi: finalQuestionHindiUrl,
                questionImageUrlEnglish: finalQuestionEnglishUrl,
                options,
                status,
                marksAwarded,
            });
        }
    }

    return questions;
}

// Exam configs (simplified)
const EXAM_CONFIGS = {
    DELHI_POLICE_HEAD_CONSTABLE: {
        id: 'DELHI_POLICE_HEAD_CONSTABLE',
        name: 'Delhi Police Head Constable (CBT)',
        displayName: 'DP Head Constable',
        emoji: '🚔',
        subjects: [
            { name: 'General Awareness', part: 'A', totalQuestions: 25, maxMarks: 25, correctMarks: 1, negativeMarks: 0.25 },
            { name: 'Quantitative Aptitude', part: 'B', totalQuestions: 20, maxMarks: 20, correctMarks: 1, negativeMarks: 0.25 },
            { name: 'Reasoning', part: 'C', totalQuestions: 25, maxMarks: 25, correctMarks: 1, negativeMarks: 0.25 },
            { name: 'English Language', part: 'D', totalQuestions: 20, maxMarks: 20, correctMarks: 1, negativeMarks: 0.25 },
            { name: 'Computer Fundamentals', part: 'E', totalQuestions: 10, maxMarks: 10, correctMarks: 1, negativeMarks: 0.25 },
        ],
        totalQuestions: 100,
        maxMarks: 100,
    },
};

async function handleRequest(req, res) {
    // Handle CORS preflight
    if (req.method === 'OPTIONS') {
        res.writeHead(200, corsHeaders);
        res.end();
        return;
    }

    if (req.method !== 'POST') {
        res.writeHead(405, corsHeaders);
        res.end(JSON.stringify({ error: 'Method not allowed' }));
        return;
    }

    let body = '';
    req.on('data', chunk => { body += chunk; });

    req.on('end', async () => {
        try {
            const { url, examType, language } = JSON.parse(body);

            console.log('Analyzing:', url, 'Exam:', examType, 'Language:', language);

            const examConfig = EXAM_CONFIGS[examType] || EXAM_CONFIGS.DELHI_POLICE_HEAD_CONSTABLE;

            // Fetch the HTML directly
            const response = await fetch(url);
            const html = await response.text();

            console.log('Fetched HTML length:', html.length);

            // Parse with the first subject config
            const subject = examConfig.subjects[0];
            const questions = parseQuestionsForPart(html, subject.part, url, subject, 0);

            console.log('Parsed questions:', questions.length);

            const result = {
                candidate: {
                    rollNumber: '',
                    name: '',
                    examLevel: examConfig.name,
                    testDate: '',
                    shift: '',
                    centreName: '',
                },
                examType,
                examConfig,
                language,
                totalScore: 0,
                maxScore: examConfig.maxMarks,
                totalQuestions: questions.length,
                correctCount: questions.filter(q => q.status === 'correct').length,
                wrongCount: questions.filter(q => q.status === 'wrong').length,
                unattemptedCount: questions.filter(q => q.status === 'unattempted').length,
                sections: [],
                questions,
            };

            res.writeHead(200, corsHeaders);
            res.end(JSON.stringify({ success: true, data: result }));

        } catch (error) {
            console.error('Error:', error);
            res.writeHead(500, corsHeaders);
            res.end(JSON.stringify({ success: false, error: error.message }));
        }
    });
}

const server = http.createServer(handleRequest);
const PORT = 3001;

server.listen(PORT, () => {
    console.log(`Local analysis server running at http://localhost:${PORT}`);
    console.log('Use POST requests with { url, examType, language } body');
});
