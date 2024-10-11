from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import pronouncing
import re

app = Flask(__name__)
CORS(app)

def count_syllables_heuristic(word):
    word = word.lower()
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
    # Handle words with apostrophes
    if "'" in word:
        parts = word.split("'")
        total_syllables = 0
        total_stress = ""
        for part in parts:
            syllables, stress = get_syllables_and_stress(part)
            total_syllables += syllables
            total_stress += stress
        return total_syllables, total_stress

    # Try Datamuse API first for syllable count
    response = requests.get(f"https://api.datamuse.com/words?sp={word}&md=s")
    if response.status_code == 200:
        data = response.json()
        if data and 's' in data[0]:
            syllables = int(data[0]['s'])
        else:
            syllables = None
    else:
        syllables = None
    
    # Use pronouncing library for stress pattern and as fallback for syllable count
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
    
    # If stress pattern is still None, use a default pattern based on syllable count
    if stress_pattern is None:
        stress_pattern = '10' * (syllables // 2) + ('1' if syllables % 2 else '')
    
    return syllables, stress_pattern

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    words = re.findall(r"\w+(?:'\w+)?|\S+", data['input'])  # This regex will keep words with apostrophes together
    expected_syllables = data['expectedSyllables']
    expected_stress = data['expectedStress']

    total_syllables = 0
    full_stress_pattern = ''
    details = []

    for word in words:
        syllables, stress_pattern = get_syllables_and_stress(word)
        
        total_syllables += syllables
        full_stress_pattern += stress_pattern
        details.append({
            "word": word,
            "syllables": syllables,
            "stress": stress_pattern
        })

    return jsonify({
        "totalSyllables": total_syllables,
        "fullStressPattern": full_stress_pattern,
        "details": details,
        "syllablesCorrect": total_syllables == expected_syllables,
        "stressCorrect": full_stress_pattern == expected_stress
    })

if __name__ == '__main__':
    app.run(debug=True)