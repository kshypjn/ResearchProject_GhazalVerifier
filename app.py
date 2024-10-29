from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import pronouncing
import re

app = Flask(__name__)
CORS(app)

def count_syllables_heuristic(word):
    word = ''.join(c for c in word.lower() if c.isalnum())
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
    word = ''.join(c for c in word if c.isalnum())
    if "'" in word:
        parts = word.split("'")
        total_syllables = 0
        total_stress = ""
        for part in parts:
            syllables, stress = get_syllables_and_stress(part)
            total_syllables += syllables
            total_stress += stress
        return total_syllables, total_stress

    response = requests.get(f"https://api.datamuse.com/words?sp={word}&md=s")
    if response.status_code == 200:
        data = response.json()
        if data and 's' in data[0]:
            syllables = int(data[0]['s'])
        else:
            syllables = None

    pronunciations = pronouncing.phones_for_word(word)
    if pronunciations:
        stresses = pronouncing.stresses(pronunciations[0])
        stress_pattern = ''.join('1' if s == '1' else '0' for s in stresses)
        if syllables is None:
            syllables = len(stresses)
    else:
        stress_pattern = None
        if syllables is None:
            syllables = count_syllables_heuristic(word)

    # Ensure that monosyllabic words have 0 stress
    if syllables == 1:
        stress_pattern = '0'
    elif stress_pattern is None:
        # Default pattern for multisyllabic words without pronunciation info
        stress_pattern = ''.join(['01'] * (syllables // 2) + ['1'] * (syllables % 2))

    return syllables, stress_pattern


def get_rhyming_words(word):
    """Get rhyming words using the Datamuse API"""
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
        input_text = data['input'].strip()
        words = re.findall(r"\w+(?:'\w+)?|\S+", input_text)
        expected_syllables = data['expectedSyllables']
        expected_stress = data['expectedStress']
        refrain = data['refrain'].strip()

        # First, analyze the refrain
        refrain_words = re.findall(r"\w+(?:'\w+)?|\S+", refrain)
        refrain_syllables = 0
        for word in refrain_words:
            syllables, _ = get_syllables_and_stress(word)
            refrain_syllables += syllables

        # Now analyze the full hemistich
        total_syllables = 0
        full_stress_pattern = ''
        details = []
        rhyming_words = []

        # Process each word in the input text
        for word in words:
            syllables, stress_pattern = get_syllables_and_stress(word)
            total_syllables += syllables
            full_stress_pattern += stress_pattern
            details.append({
                "word": word,
                "syllables": syllables,
                "stress": stress_pattern
            })

        # Find the rhyming word before the refrain
        if refrain_syllables > 0:
            # Find where the refrain words start
            refrain_words_set = set(refrain_words)
            
            # Go backwards through the words until we find the first word that's not in the refrain
            rhyming_word_index = -1
            for i in range(len(words) - 1, -1, -1):
                if words[i] not in refrain_words_set:
                    rhyming_word_index = i
                    break
            
            # Get rhyming words for the identified word
            if rhyming_word_index >= 0:
                rhyming_word = words[rhyming_word_index]
                print(f"Finding rhyming words for: {rhyming_word}")  # Added console logging
                rhyming_words = get_rhyming_words(rhyming_word)

        syllables_correct = total_syllables == expected_syllables
        stress_correct = full_stress_pattern == expected_stress

        return jsonify({
            "totalSyllables": total_syllables,
            "fullStressPattern": full_stress_pattern,
            "details": details,
            "syllablesCorrect": syllables_correct,
            "stressCorrect": stress_correct,
            "rhymingWords": rhyming_words,
            "refrainSyllables": refrain_syllables
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)