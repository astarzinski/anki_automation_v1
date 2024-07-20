import os
import re
import pdfplumber
import pypandoc
import docx
import pickle
from datetime import datetime
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import requests
import json
import sys
import numpy as np
import csv

# AnkiConnect URL
ANKI_CONNECT_URL = 'http://localhost:8765'

# Function to call AnkiConnect
def invoke(action, params={}):
    request_payload = json.dumps({
        'action': action,
        'version': 6,
        'params': params
    })
    response = requests.post(ANKI_CONNECT_URL, data=request_payload)
    if response.status_code != 200:
        raise Exception(f"AnkiConnect API request failed with status code {response.status_code}")
    response_json = response.json()
    if response_json.get('error'):
        raise Exception(response_json['error'])
    return response_json['result']

# Function to get tags of a note
def get_note_tags(note_id):
    note_info = invoke('notesInfo', {'notes': [note_id]})
    return note_info[0]['tags']

# Function to update tags of a note
def update_note_tags(note_id, new_tags):
    current_tags = get_note_tags(note_id)
    added_tags_count = 0
    already_present_tags_count = 0
    added_tags = []
    for tag in new_tags:
        if tag not in current_tags:
            current_tags.append(tag)
            added_tags_count += 1
            added_tags.append(tag)
        else:
            already_present_tags_count += 1
    invoke('updateNoteTags', {'note': note_id, 'tags': current_tags})
    return added_tags_count, already_present_tags_count, added_tags

# Function to suspend or unsuspend cards
def set_card_suspend(note_ids, suspend):
    total_cards = 0
    already_processed_cards = 0
    card_status = {}
    for note_id in note_ids:
        card_ids = invoke('findCards', {'query': f'nid:{note_id}'})
        if card_ids:
            card_info = invoke('cardsInfo', {'cards': card_ids})
            for card in card_info:
                if (suspend and not card['queue'] == -1) or (not suspend and card['queue'] == -1):
                    if suspend:
                        invoke('suspend', {'cards': [card['cardId']]})
                        card_status[card['cardId']] = 'suspended'
                    else:
                        invoke('unsuspend', {'cards': [card['cardId']]})
                        card_status[card['cardId']] = 'unsuspended'
                    total_cards += 1
                else:
                    already_processed_cards += 1
                    card_status[card['cardId']] = 'already processed'
    return total_cards, already_processed_cards, card_status

# Program 1: Dynamic text file preprocessing

def extract_text_pdfplumber(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    return text

def extract_text_txt(txt_path):
    with open(txt_path, 'r') as file:
        text = file.read()
    return text

def extract_text_rtf(rtf_path):
    try:
        text = pypandoc.convert_file(rtf_path, 'plain')
    except RuntimeError:
        print(f"Error processing {rtf_path} with pypandoc.")
        text = ""
    return text

def extract_text_docx(docx_path):
    doc = docx.Document(docx_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

def clean_text(text):
    # Replace Greek letters with associated words
    greek_to_words = {
        'α': 'alpha', 'Α': 'alpha', '⍺': 'alpha',
        'β': 'beta', 'Β': 'beta', 'ϐ': 'beta',
        'γ': 'gamma', 'Γ': 'gamma',
        'δ': 'delta', 'Δ': 'delta',
        'ε': 'epsilon', 'Ε': 'epsilon',
        'ζ': 'zeta', 'Ζ': 'zeta',
        'η': 'eta', 'Η': 'eta',
        'θ': 'theta', 'Θ': 'theta',
        'ι': 'iota', 'Ι': 'iota',
        'κ': 'kappa', 'Κ': 'kappa',
        'λ': 'lambda', 'Λ': 'lambda',
        'μ': 'mu', 'Μ': 'mu',
        'ν': 'nu', 'Ν': 'nu',
        'ξ': 'xi', 'Ξ': 'xi',
        'ο': 'omicron', 'Ο': 'omicron',
        'π': 'pi', 'Π': 'pi',
        'ρ': 'rho', 'Ρ': 'rho',
        'σ': 'sigma', 'Σ': 'sigma',
        'τ': 'tau', 'Τ': 'tau',
        'υ': 'upsilon', 'Υ': 'upsilon',
        'φ': 'phi', 'Φ': 'phi',
        'χ': 'chi', 'Χ': 'chi',
        'ψ': 'psi', 'Ψ': 'psi',
        'ω': 'omega', 'Ω': 'omega'
    }
    for greek, word in greek_to_words.items():
        text = text.replace(greek, word)
    return text

def preprocess_text(text):
    text = clean_text(text)
    text = text.lower()
    text = re.sub(r'[^ -~]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def save_text_to_file(directory, filename, text):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), 'w') as file:
        file.write(text)

def list_files(script_dir):
    input_dir = os.path.join(script_dir, 'input')
    file_types = ['.pdf', '.txt', '.rtf', '.docx']
    files = [f for f in os.listdir(input_dir) if any(f.endswith(ext) for ext in file_types)]
    print()
    if not files:
        print("\nNo suitable files found in the 'input' directory.")
        sys.exit(1)
    print('∆' * 40)
    print("\nFiles found in the 'input' directory:\n")
    for idx, file in enumerate(files):
        print(f"{idx + 1}. {file}")
    return files, input_dir

def main_preprocessing():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    files, input_dir = list_files(script_dir)
    if not files:
        return None
    
    choice = input("\nEnter the number of the file you want to process: ")
    try:
        file_path = os.path.join(input_dir, files[int(choice) - 1])
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            print(f"\nProcessing {file_path} with pdfplumber:")
            text = extract_text_pdfplumber(file_path)
        elif ext == '.txt':
            print(f"\nProcessing {file_path} as a text file:")
            text = extract_text_txt(file_path)
        elif ext == '.rtf':
            print(f"\nProcessing {file_path} with pypandoc:")
            text = extract_text_rtf(file_path)
        elif ext == '.docx':
            print(f"\nProcessing {file_path} with python-docx:")
            text = extract_text_docx(file_path)
        else:
            print("Unsupported file type.")
            return None
        
        preprocessed_text = preprocess_text(text)
        timestamp = datetime.now().strftime('%Y_%b_%d_%H_%M')
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        output_filename = f'{base_filename}_{timestamp}_output.txt'
        save_text_to_file(os.path.join(script_dir, 'debugging'), output_filename, preprocessed_text)
        print(f"Output saved to 'debugging/{output_filename}'")
        return os.path.join(script_dir, 'debugging', output_filename)
        
    except (IndexError, ValueError):
        print("Invalid choice. Please enter a valid number.")
    except Exception as e:
        print(f"Failed with error: {e}")
    return None

# Program 2: Embed creation and pickling

def create_embeddings(file_path):

    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
    
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    frames = divide_text_into_frames(text, 30, 5)
    embeddings = model.encode(frames, show_progress_bar=True)
    
    pickle_file = os.path.join(os.path.dirname(os.path.dirname(file_path)), 'pickle', 'pdf_text_embeddings.pkl')
    with open(pickle_file, 'wb') as f:
        pickle.dump(embeddings, f)

    print(f"Embeddings saved to {pickle_file}")
    return pickle_file

# Program 3: Embed comparison and scoring

def divide_text_into_frames(text, frame_size, step_size):
    words = text.split()
    frames = []
    for i in range(0, len(words) - frame_size + 1, step_size):
        frame = ' '.join(words[i:i + frame_size])
        frames.append(frame)
    return frames

def compare_embeddings():
    current_directory = os.path.dirname(os.path.abspath(__file__))
    
    note_cards_pickle_file = os.path.join(current_directory, 'pickle', 'note_card_embeddings.pkl')
    pdf_text_pickle_file = os.path.join(current_directory, 'pickle', 'pdf_text_embeddings.pkl')
    
    with open(note_cards_pickle_file, 'rb') as f:
        note_card_ids, note_card_embeddings = pickle.load(f)

    with open(pdf_text_pickle_file, 'rb') as f:
        pdf_text_embeddings = pickle.load(f)
    
    similarity = cosine_similarity(pdf_text_embeddings, note_card_embeddings)
    
    # Calculate average similarity score for each note
    average_scores = np.mean(similarity, axis=0)
    
    similarities_list = [(note_card_ids[i], average_scores[i]) for i in range(average_scores.shape[0])]
    similarities_list.sort(key=lambda x: x[1], reverse=True)
    
    top_similarities = similarities_list[:1001]
    
    note_cards_file = os.path.join(current_directory, 'debugging', 'note_id_text.txt')
    with open(note_cards_file, 'r', encoding='utf-8') as file:
        note_cards = eval(file.read())

    note_card_dict = {id: text for id, text in note_cards}
    print("~" * 80)
    print("~" * 80)
    print("~" * 80)
    print(f"{'Index':<6} {'Score':<10} {'Note ID':<15} {'Text'}")
    print("~" * 80)
    for i, (note_id, score) in enumerate(reversed(top_similarities)):
        original_index = len(top_similarities) - 1 - i
        if original_index <= 25:
            print(f"\033[91m{original_index:<6} {score:<10.4f} {note_id:<15} {note_card_dict[note_id]}\033[0m")
        elif original_index <= 100 and original_index % 5 == 0:
            print(f"\033[93m{original_index:<6} {score:<10.4f} {note_id:<15} {note_card_dict[note_id]}\033[0m")
        elif original_index <= 200 and original_index % 10 == 0:
            print(f"\033[92m{original_index:<6} {score:<10.4f} {note_id:<15} {note_card_dict[note_id]}\033[0m")
        elif original_index > 200 and original_index <= 500 and original_index % 25 == 0:
            print(f"\033[94m{original_index:<6} {score:<10.4f} {note_id:<15} {note_card_dict[note_id]}\033[0m")
        elif original_index <= 1000 and original_index % 100 == 0:
            print(f"\033[95m{original_index:<6} {score:<10.4f} {note_id:<15} {note_card_dict[note_id]}\033[0m")
        else:
            continue
        print("~" * 80)
    print(f"{'^Index':<6} {'^Score':<10} {'^Note ID':<15} {'^Text'}")
    print("~" * 80)
    try:
        cutoff_index = int(input("Enter the cutoff index --select the first dissimilar card to avoid missing relevant cards-- : "))
        if cutoff_index < 0 or cutoff_index >= len(top_similarities):
            raise ValueError("Index out of range.")
    except ValueError:
        print("Invalid index. Exiting the program.")
        sys.exit(1)
    
    above_cutoff = [(note_id, score) for i, (note_id, score) in enumerate(top_similarities) if i <= cutoff_index]
    
    print("\nList of Note IDs and their texts above the cutoff point:")
    print('-' * 80)
    for note_id, score in above_cutoff:
        print(f"Note ID: {note_id}, Score: {score}")
        print(f"Text: {note_card_dict[note_id]}")
        print('-' * 80)

    return [note_id for note_id, score in above_cutoff], note_card_dict

def update_anki(note_ids, note_card_dict):
    print("Choose an action (or press enter to do nothing):")
    print("1. Tag the notes")
    print("2. Unsuspend the cards")
    print("3. Tag the notes and unsuspend the cards")
    print('*' * 40)
    action_input = input("Enter the number of the action you want to perform: ")
    print('*' * 40)
    if not action_input:
        print("No action selected. Exiting.")
        return

    action = int(action_input)

    tagged_notes_count = 0
    already_present_tags_count = 0
    unsuspended_cards_count = 0
    already_unsuspended_cards_count = 0
    output_data = []

    if action == 1:
        new_tags_input = input("Enter the new tags to add (comma-separated): ")
        new_tags = [tag.strip() for tag in new_tags_input.split(',')]
        for note_id in note_ids:
            added_tags_count, already_tags_count, added_tags = update_note_tags(note_id, new_tags)
            tagged_notes_count += added_tags_count
            already_present_tags_count += already_tags_count

            # Get the note text
            note_text = note_card_dict[note_id]

            # Find card IDs
            card_ids = invoke('findCards', {'query': f'nid:{note_id}'})
            for card_id in card_ids:
                output_data.append((note_id, card_id, note_text, added_tags, ''))

    elif action == 2:
        total_cards, already_processed_cards, card_status = set_card_suspend(note_ids, suspend=False)
        unsuspended_cards_count += total_cards
        already_unsuspended_cards_count += already_processed_cards

        for note_id in note_ids:
            # Get the note text
            note_text = note_card_dict[note_id]

            # Find card IDs
            card_ids = invoke('findCards', {'query': f'nid:{note_id}'})
            for card_id in card_ids:
                if card_id in card_status:
                    output_data.append((note_id, card_id, note_text, '', card_status[card_id]))

    elif action == 3:
        new_tags_input = input("Enter the new tags to add (comma-separated): ")
        new_tags = [tag.strip() for tag in new_tags_input.split(',')]
        for note_id in note_ids:
            added_tags_count, already_tags_count, added_tags = update_note_tags(note_id, new_tags)
            tagged_notes_count += added_tags_count
            already_present_tags_count += already_tags_count

            # Get the note text
            note_text = note_card_dict[note_id]

            # Find card IDs
            card_ids = invoke('findCards', {'query': f'nid:{note_id}'})
            for card_id in card_ids:
                output_data.append((note_id, card_id, note_text, added_tags, ''))

        total_cards, already_processed_cards, card_status = set_card_suspend(note_ids, suspend=False)
        unsuspended_cards_count += total_cards
        already_unsuspended_cards_count += already_processed_cards

        for note_id in note_ids:
            # Get the note text
            note_text = note_card_dict[note_id]

            # Find card IDs
            card_ids = invoke('findCards', {'query': f'nid:{note_id}'})
            for card_id in card_ids:
                if card_id in card_status:
                    # Update the existing tuple with card status
                    for i, record in enumerate(output_data):
                        if record[1] == card_id:
                            output_data[i] = (record[0], record[1], record[2], record[3], card_status[card_id])

    # Save the output data to a CSV file with a timestamp
    timestamp = datetime.now().strftime('%Y_%b_%d_%H_%M')
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    output_filename = f'anki_modifications_output_{timestamp}.csv'
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, output_filename), 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        # Write header
        csv_writer.writerow(['Note ID', 'Card ID', 'Note Text', 'Added Tags', 'Card Status'])
        # Write data
        for record in output_data:
            csv_writer.writerow(record)

    if action not in [1, 2, 3]:
        print("Invalid action.")
    else:
        print('*' * 40)
        print(f"{'Notes with new tag:':<32} \033[91m{tagged_notes_count}\033[0m")
        print('-' * 40)
        print(f"{'Notes already tagged:':<32} \033[91m{already_present_tags_count}\033[0m")
        print('-' * 40)
        print(f"{'Newly unsuspended cards:':<32} \033[91m{unsuspended_cards_count}\033[0m")
        print('-' * 40)
        print(f"{'Previously unsuspended cards:':<32} \033[91m{already_unsuspended_cards_count}\033[0m")
        print('-' * 40)
        print(f"Output saved to 'output/{output_filename}'")

# Main execution flow

if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pickle'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debugging'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'input'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output'), exist_ok=True)
    print('This program will only run if you have already processed and embedded your Anki deck!!!\n')
    input(f'Place the document(s) you would like to process in {os.path.join(os.path.dirname(os.path.abspath(__file__)), "input")}\n\033[92mPress <return> when ready\033[0m')
    processed_file = main_preprocessing()
    if processed_file:
        embeddings_file = create_embeddings(processed_file)
        if embeddings_file:
            note_ids, note_card_dict = compare_embeddings()
            if note_ids:
                update_anki(note_ids, note_card_dict)
