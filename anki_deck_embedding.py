import requests
import json
import re
import os
import sys
import pickle
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

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

# Function to get all note IDs in a specific deck
def get_all_notes_in_deck(deck_name):
    note_ids = invoke('findNotes', {'query': f'deck:"{deck_name}"'})
    print(f"Found {len(note_ids)} notes in deck '{deck_name}'.")
    return note_ids

# Function to remove specific patterns from text
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
    
    # Replace HTML entities with appropriate words and ensure spacing
    html_entities = {
        '&lt;': ' less than ',
        '&gt;': ' greater than ',
        '&amp;': ' and '
    }
    for entity, replacement in html_entities.items():
        text = text.replace(entity, replacement)
    
    # Remove non-breaking space entities
    text = re.sub('&nbsp;', ' ', text)
    
    # Add space before patterns if not already present
    text = re.sub(r'(\S)(\{\{c\d+::)', r'\1 \2', text)
    
    # Retain the desired part of the patterns including special characters
    text = re.sub(r'\{\{c\d+::(.*?)(?:::[^}]*)?\}\}', r'\1', text)
    
    # Replace HTML break and div tags with spaces
    text = re.sub(r'<br\s*/?>', ' ', text)
    text = re.sub(r'</div><div>', ' ', text)
    text = re.sub(r'<div>', ' ', text)
    text = re.sub(r'</div>', ' ', text)
    
    # Remove any remaining HTML tags
    text = re.sub('<.*?>', '', text).strip()
    
    # Replace newline characters with spaces
    text = text.replace('\n', ' ').replace('\r\n', ' ')
    
    # Normalize spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Ensure spaces around parentheses
    text = re.sub(r'\(', ' (', text)
    text = re.sub(r'\)', ') ', text)
    
    # Normalize spaces again after adding spaces around parentheses
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Make all text lowercase
    text = text.lower()

    # Remove any non-ASCII characters
    text = re.sub(r'[^ -~]+', ' ', text)
    
    return text

# Function to get the first part of the text of a note and clean it
def get_note_text(note_id):
    note_info = invoke('notesInfo', {'notes': [note_id]})
    fields = note_info[0]['fields']
    first_field = next(iter(fields.values()))['value']
    text = first_field.split('|')[0]
    text = clean_text(text)
    return text

# Function to check if embeddings exist and ask user for update
def check_for_embeddings(pickle_file):
    if os.path.exists(pickle_file):
        while True:
            choice = input(f"Embeddings file '{pickle_file}' already exists. Do you want to recreate it? (y/n): ").strip().lower()
            if choice in ['y', 'n']:
                return choice == 'y'
            print("Invalid input. Please enter 'y' or 'n'.")
    return True

# Function to save note tuples to a file
def save_note_tuples(file_path, note_tuples):
    with open(file_path, 'w') as f:
        f.write(str(note_tuples))

if __name__ == '__main__':

    # Create directories if they do not exist
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pickle'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debugging'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'input'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output'), exist_ok=True)

    # Embedding file path
    pickle_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pickle', 'note_card_embeddings.pkl')

    # Check if embeddings already exist and ask user for update
    if not check_for_embeddings(pickle_file):
        print(f"Using existing embeddings from {pickle_file}")
        sys.exit(1)

    # Get the list of decks
    decks = invoke('deckNames')
    if not decks:
        print("No decks found in Anki.")
        sys.exit(1)

    # Present the list of decks to the user
    print("Available decks:")
    for i, deck in enumerate(decks):
        print(f"{i + 1}. {deck}")

    # Get the user's choice of deck
    try:
        deck_choice = int(input("Enter the number of the deck you want to process: ")) - 1
        if deck_choice < 0 or deck_choice >= len(decks):
            print("Invalid choice.")
            sys.exit(1)
    except ValueError:
        print("Invalid input. Please enter a number.")
        sys.exit(1)

    selected_deck = decks[deck_choice]
    print(f"Selected deck: {selected_deck}")

    # Get all notes in the selected deck
    note_ids_in_deck = get_all_notes_in_deck(selected_deck)
    print(f"Total number of notes in deck '{selected_deck}': {len(note_ids_in_deck)}")

    # Lists to hold the tuples of noteID and text, noteID, and texts
    note_tuples = []
    note_card_ids = []
    note_card_texts = []

    # Process each note in the selected deck
    for note_id in tqdm(note_ids_in_deck, desc="Processing notes", unit="note"):
        text = get_note_text(note_id)
        note_tuples.append((note_id, text))
        note_card_ids.append(note_id)
        note_card_texts.append(text)

    # Save original note tuples to a file
    original_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debugging', f'note_id_text.txt')
    save_note_tuples(original_file_path, note_tuples)
    print(f"Original note tuples saved to {original_file_path}")

    # Load the model
    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

    # Generate embeddings for the note cards
    embeddings = model.encode(note_card_texts, batch_size=32, show_progress_bar=True)

    # Save embeddings and IDs to a pickle file
    with open(pickle_file, 'wb') as f:
        pickle.dump((note_card_ids, note_card_texts, embeddings), f)

    print(f"Embeddings saved to {pickle_file}")