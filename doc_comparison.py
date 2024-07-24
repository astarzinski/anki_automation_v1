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

ANKI_CONNECT_URL = 'http://localhost:8765'

# PDF Extraction
def extract_text_pdfplumber(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    return text

# TXT Extraction
def extract_text_txt(txt_path):
    with open(txt_path, 'r') as file:
        text = file.read()
    return text

# RTF Extraction
def extract_text_rtf(rtf_path):
    try:
        text = pypandoc.convert_file(rtf_path, 'plain')
    except RuntimeError:
        print(f"Error processing {rtf_path} with pypandoc.")
        text = ""
    return text

# WORD DOC Extraction
def extract_text_docx(docx_path):
    doc = docx.Document(docx_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

# Normalize text for embedding
def preprocess_text(text):
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

    # Makes all text lowercase
    text = text.lower()

    # Remove any non-ASCII characters
    text = re.sub(r'[^ -~]+', ' ', text)

    # Remove extra blank space
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Save a file for debugging
def save_text_to_file(directory, filename, text):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), 'w') as file:
        file.write(text)

# Present the user with a list of files
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

# Uses the above functions to preprocess a selected text document for embedding
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
        return preprocessed_text
        
    except (IndexError, ValueError):
        print("Invalid choice. Please enter a valid number.")
    except Exception as e:
        print(f"Failed with error: {e}")
    return None

# Embed creation
def create_embeddings(text):

    # Defines the LLM that is being used
    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

    # Defines the size and steps of a shifiting reading frame that is used in embedding
    frame_size = 30
    step_size = 5

    # Uses the defined reading frame to divide the text
    words = text.split()
    frames = []
    for i in range(0, len(words) - frame_size + 1, step_size):
        frame = ' '.join(words[i:i + frame_size])
        frames.append(frame)
    
    # Each frame is embedded separately
    embeddings = model.encode(frames, show_progress_bar=True)
    return embeddings

# Compares the newly embedded document to the previously embedded and serialized anki deck
def compare_embeddings(pdf_text_embeddings):
    current_directory = os.path.dirname(os.path.abspath(__file__))
    
    # Access the embedded anki deck
    note_cards_pickle_file = os.path.join(current_directory, 'pickle', 'note_card_embeddings.pkl')
    with open(note_cards_pickle_file, 'rb') as f:
        note_card_ids, note_card_text, note_card_embeddings = pickle.load(f)
    
    # Create a similarity matrix frames x notes
    similarity = cosine_similarity(pdf_text_embeddings, note_card_embeddings)
    
    # Calculate average similarity score for each note
    average_scores = np.mean(similarity, axis=0)
    
    # Create a tuple list that contains note ID and score for all notes
    similarities_list = [(average_scores[i], note_card_ids[i], note_card_text[i]) for i in range(average_scores.shape[0])]
    
    # Sort the list in descending score order
    similarities_list.sort(key=lambda x: x[0], reverse=True)
    
    # Take the first 250 items of the sorted list
    top_similarities = similarities_list[:250]
    
    # Print the list in reverse so the highest scored notes are closest to the user input point
    print("~" * 40)
    print(f"{'Index':<6} {'Score':<10} {'Note ID':<15} {'Text'}")
    print("~" * 40)
    for i, (score, note_id, note_text) in enumerate(reversed(top_similarities)):
        original_index = len(top_similarities) - i
        print(f"\033[91m{original_index:<6} {score:<10.4f} {note_id:<15} {note_text}\033[0m")
        print("~" * 40)
    print(f"{'^Index':<6} {'^Score':<10} {'^Note ID':<15} {'^Text'}")
    print("~" * 40)

    # Ask the user for a cutoff index
    while True:
        cutoff_index = input("Enter the cutoff index or enter nothing and press <return> to exit without making changes: ")
        if not cutoff_index:
            print("Nothing was entered. Exiting the program.")
            sys.exit(1)
        try:
            cutoff_index = int(cutoff_index)
            assert cutoff_index >= 1 and cutoff_index <= len(top_similarities)
            break
        except:
            print("Invalid index.")
    
    # Create a list of the selected notes
    above_cutoff = [(score, note_id, note_text) for i, (score, note_id, note_text) in enumerate(top_similarities) if i <= cutoff_index - 1]
    
    # Print data for the selected notes
    print("\nList of Note IDs and their texts above the cutoff point:")
    print('-' * 40)
    for score, note_id, note_text in above_cutoff:
        print(f"Note ID: {note_id}, Score: {score}")
        print(f"Text: {note_text}")
        print('-' * 40)
    
    return [(note_id, note_text) for score, note_id, note_text in above_cutoff]

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

# Function to update tags of a note
def update_note_tags(note_id, new_tags):
    # Access the information for a given note ID
    note_info = invoke('notesInfo', {'notes': [note_id]})

    # Identify the existing tags on the note
    current_tags = note_info[0]['tags']

    # Initialize variables for tracking tag changes
    added_tags_count = 0
    already_present_tags_count = 0
    added_tags = []

    # Iterate through user provided tags and add only new tags to the note
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
def set_card_suspend(note_id_text):

    # Initialize variables for tracking suspension status changes
    unsuspended_cards = 0
    already_processed_cards = 0
    card_status = {}

    # Iterate through the note IDs
    for note_id, note_text in note_id_text:
        card_ids = invoke('findCards', {'query': f'nid:{note_id}'})

        # Identify all cards derrived from a given note
        if card_ids:
            card_info = invoke('cardsInfo', {'cards': card_ids})
            for card in card_info:
                # If a card is suspended, unsuspend it
                if card['queue'] == -1:
                    invoke('unsuspend', {'cards': [card['cardId']]})
                    card_status[card['cardId']] = 'unsuspended'
                    unsuspended_cards += 1
                else:
                    already_processed_cards += 1
                    card_status[card['cardId']] = 'already processed'

    return unsuspended_cards, already_processed_cards, card_status

# Main function for interacting with a users anki data
def update_anki(note_id_text):

    # Ask the user to identify how they would like to modify their anki data for the selected notes
    print("Choose an action (or press enter to do nothing):")
    print("1. Tag the notes")
    print("2. Unsuspend the cards")
    print("3. Tag the notes and unsuspend the cards")
    print('*' * 40)
    while True:
        action_input = input("Enter the number of the action you want to perform, \nor enter nothing and press <return> to exit without making changes: ")
        print('*' * 40)
        if not action_input:
            print("No action selected. Exiting.")
            return
        try:
            action = int(action_input)
            break
        except:
            print('Enter "1", "2", or "3".')

    # Initialize variables to track anki data changes
    tagged_notes_count = 0
    already_present_tags_count = 0
    unsuspended_cards_count = 0
    already_unsuspended_cards_count = 0
    output_data = []

    # Workflow for only adding tags
    if action == 1:

        # Get tag(s) from user input
        new_tags_input = input("Enter the new tags to add (comma-separated) or press <return> to exit without making changes:")
        if not new_tags_input:
            print("No tag(s) entered. Exiting")
            return
        
        # Process user input
        new_tags = [tag.strip() for tag in new_tags_input.split(',')]

        # Iterate through all note IDs to add tag(s)
        for note_id, note_text in note_id_text:
            added_tags_count, already_tags_count, added_tags = update_note_tags(note_id, new_tags)

            # Update modification scores
            tagged_notes_count += added_tags_count
            already_present_tags_count += already_tags_count

            # Find card IDs to update data modification output
            card_ids = invoke('findCards', {'query': f'nid:{note_id}'})
            for card_id in card_ids:
                output_data.append((note_id, card_id, note_text, added_tags, ''))

    # Workflow for only unsuspending cards
    elif action == 2:

        # Call function to unsuspend all suspended cards for each note
        unsuspended_cards, already_processed_cards, card_status = set_card_suspend(note_id_text)

        # Update modification scores
        unsuspended_cards_count += unsuspended_cards
        already_unsuspended_cards_count += already_processed_cards

        # Find card IDs to update data modification output
        for note_id, note_text in note_id_text:
            card_ids = invoke('findCards', {'query': f'nid:{note_id}'})
            for card_id in card_ids:
                if card_id in card_status:
                    output_data.append((note_id, card_id, note_text, '', card_status[card_id]))

    # Workflow for tagging and unsuspending cards 
    elif action == 3:

        # Get tag(s) from user input
        new_tags_input = input("Enter the new tags to add (comma-separated) or press <return> to exit without making changes:")
        if not new_tags_input:
            print("No tag(s) entered. Exiting")
            return
        
        # Process user input
        new_tags = [tag.strip() for tag in new_tags_input.split(',')]

         # Iterate through all note IDs to add tag(s)
        for note_id, note_text in note_id_text:
            added_tags_count, already_tags_count, added_tags = update_note_tags(note_id, new_tags)
            
            # Update modification scores
            tagged_notes_count += added_tags_count
            already_present_tags_count += already_tags_count

            # Find card IDs to update data modification output
            card_ids = invoke('findCards', {'query': f'nid:{note_id}'})
            for card_id in card_ids:
                output_data.append((note_id, card_id, note_text, added_tags, ''))

        # Call function to unsuspend all suspended cards for each note
        unsuspended_cards, already_processed_cards, card_status = set_card_suspend(note_id_text)
        
        # Update modification scores
        unsuspended_cards_count += unsuspended_cards
        already_unsuspended_cards_count += already_processed_cards

        # Find card IDs to update data modification output
        for note_id, note_text in note_id_text:
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
    with open(os.path.join(output_dir, output_filename), 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)

        # Write header
        csv_writer.writerow(['Note ID', 'Card ID', 'Note Text', 'Added Tags', 'Card Status'])
        
        # Write data
        for record in output_data:
            csv_writer.writerow(record)

    # Display data for anki changes
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
    raw_text = main_preprocessing()
    if raw_text:
        embedded_text = create_embeddings(raw_text)
        note_id_text = compare_embeddings(embedded_text)
        update_anki(note_id_text)