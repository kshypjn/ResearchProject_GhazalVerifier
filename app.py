from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import pronouncing
import re

app = Flask(__name__)
CORS(app)

def clean_text(text):
    text = re.sub(r'([a-zA-Z0-9])([.,!?;:])', r'\1 \2', text)
    text = re.sub(r'([.,!?;:])([a-zA-Z0-9])', r'\1 \2', text)
    return text

def strip_punctuation(text):
    return re.sub(r'[.,!?;:]', '', text)

def check_refrain_at_end(input_text, refrain):
    input_text = input_text.strip()
    refrain = refrain.strip()
    clean_input = strip_punctuation(input_text)
    clean_refrain = strip_punctuation(refrain)
    return clean_input.endswith(clean_refrain)

def count_syllables_heuristic(word):
    if "'" in word:
        return 2
    word = ''.join(c for c in word.lower() if c.isalnum())
    if not word:
        return 0
    count = 0
    vowels = 'aeiouy'
    if word[0] in vowels:
        count += 1
    for index in range(1, len(word)):
        if word[index] in vowels and word[index - 1] not in vowels:
            count += 1
    if word.endswith('e'):
        count -= 1
    if word.endswith('le') and len(word) > 2 and word[-3] not in vowels:
        count += 1
    if count == 0:
        count += 1
    return count

def get_syllables_and_stress(word):
    if not any(c.isalnum() for c in word):
        return 0, ""
    if "'" in word:
        return 2, "01"
    word = ''.join(c for c in word if c.isalnum())
    if not word:
        return 0, ""
    response = requests.get(f"https://api.datamuse.com/words?sp={word}&md=s")
    if response.status_code == 200:
        data = response.json()
        if data and 's' in data[0]:
            syllables = int(data[0]['s'])
        else:
            syllables = count_syllables_heuristic(word)
    else:
        syllables = count_syllables_heuristic(word)
    pronunciations = pronouncing.phones_for_word(word)
    if pronunciations:
        stresses = pronouncing.stresses(pronunciations[0])
        stress_pattern = ''.join('1' if s == '1' else '0' for s in stresses)
    else:
        if syllables == 1:
            stress_pattern = '1'
        elif syllables == 2:
            stress_pattern = '01'
        else:
            stress_pattern = '0' + '10' * ((syllables - 1) // 2)
            if syllables % 2 == 0:
                stress_pattern += '1'
    return syllables, stress_pattern

def get_rhyming_words(word):
    word = ''.join(c for c in word if c.isalnum())
    if not word:
        return []
    response = requests.get(f"https://api.datamuse.com/words?rel_rhy={word}&max=5")
    if response.status_code == 200:
        data = response.json()
        return [item['word'] for item in data]
    return []

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/verify', methods=['POST'])
def verify():
    try:
        data = request.json
        input_text = clean_text(data['input'].strip())
        words = re.findall(r"\S+", input_text)
        expected_syllables = data['expectedSyllables']
        expected_stress = data['expectedStress']
        refrain = clean_text(data['refrain'].strip())

        refrain_exists = check_refrain_at_end(input_text, refrain)
        
        refrain_words = re.findall(r"\S+", strip_punctuation(refrain))
        refrain_syllables = 0
        for word in refrain_words:
            syllables, _ = get_syllables_and_stress(word)
            refrain_syllables += syllables

        total_syllables = 0
        full_stress_pattern = ''
        details = []
        rhyming_words = []

        for word in words:
            syllables, stress_pattern = get_syllables_and_stress(word)
            total_syllables += syllables
            full_stress_pattern += stress_pattern
            details.append({
                "word": word,
                "syllables": syllables,
                "stress": stress_pattern
            })

        if refrain_syllables > 0 and refrain_exists:
            input_without_refrain = strip_punctuation(input_text[:-(len(strip_punctuation(refrain)))]).strip()
            words_before_refrain = re.findall(r"\S+", input_without_refrain)
            if words_before_refrain:
                last_word_before_refrain = words_before_refrain[-1]
                rhyming_words = get_rhyming_words(last_word_before_refrain)

        syllables_correct = total_syllables == expected_syllables
        stress_correct = full_stress_pattern == expected_stress

        return jsonify({
            "totalSyllables": total_syllables,
            "fullStressPattern": full_stress_pattern,
            "details": details,
            "syllablesCorrect": syllables_correct,
            "stressCorrect": stress_correct,
            "rhymingWords": rhyming_words,
            "refrainSyllables": refrain_syllables,
            "refrainExists": refrain_exists,
            "refrainMessage": "Refrain must appear at the end of the text" if not refrain_exists else None
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
