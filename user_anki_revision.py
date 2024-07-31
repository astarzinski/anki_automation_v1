import os
import json
import requests
import csv
import ast
from datetime import datetime

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
    note_info = invoke('notesInfo', {'notes': [int(note_id)]})
    return note_info[0]['tags']

# Function to update tags of a note
def update_note_tags(note_id, new_tags):
    current_tags = get_note_tags(note_id)
    for tag in new_tags:
        if tag not in current_tags:
            current_tags.append(tag)
    invoke('updateNoteTags', {'note': int(note_id), 'tags': current_tags})

# Function to remove tags from a note
def remove_note_tags(note_id, tags_to_remove):
    current_tags = get_note_tags(note_id)
    updated_tags = [tag for tag in current_tags if tag not in tags_to_remove]
    invoke('updateNoteTags', {'note': int(note_id), 'tags': updated_tags})

# Function to suspend or unsuspend cards
def set_card_suspend(note_ids, suspend):
    for note_id in note_ids:
        card_ids = invoke('findCards', {'query': f'nid:{int(note_id)}'})
        if card_ids:
            card_info = invoke('cardsInfo', {'cards': card_ids})
            for card in card_info:
                if (suspend and not card['queue'] == -1) or (not suspend and card['queue'] == -1):
                    if suspend:
                        invoke('suspend', {'cards': [card['cardId']]})
                    else:
                        invoke('unsuspend', {'cards': [card['cardId']]})

# Function to load modification files
def load_modification_files(output_dir):
    files = [f for f in os.listdir(output_dir) if f.startswith('anki_modifications_output_') and f.endswith('.csv')]
    return files

# Function to parse the modification file into a list of dictionaries
def parse_modification_file(filepath):
    modifications = []
    with open(filepath, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Convert the 'Added Tags' column from a string representation of a list to an actual list
            try:
                row['Added Tags'] = ast.literal_eval(row['Added Tags'])
            except (ValueError, SyntaxError):
                row['Added Tags'] = []
            modifications.append(row)
    return modifications

# Function to generate output file
def generate_output_file(modifications, header):
    timestamp = datetime.now().strftime('%Y_%b_%d_%H_%M')
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    output_filename = f'anki_modifications_output_rev_{timestamp}.csv'
    output_filepath = os.path.join(output_dir, output_filename)
    with open(output_filepath, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=header)
        writer.writeheader()
        for mod in modifications:
            # Convert the 'Added Tags' list back to a string representation
            mod['Added Tags'] = str(mod['Added Tags'])
            writer.writerow(mod)
    print(f"Output saved to {output_filepath}")

# Prints, in red, the notes that have been selected by the user for modification.
def print_modifications(modifications, selected_indices):
    unique_modifications = []
    seen_note_ids = set()
    for mod in modifications:
        if mod['Note ID'] not in seen_note_ids:
            unique_modifications.append(mod)
            seen_note_ids.add(mod['Note ID'])

    for idx, mod in enumerate(unique_modifications):
        note_id, note_text, tags = mod['Note ID'], mod['Note Text'], mod['Added Tags']
        if idx in selected_indices:
            print(f"\033[91m{idx+1}. Note ID: {note_id}, Note Text: {note_text}, Added Tags: {tags}\033[0m")
        else:
            print(f"{idx+1}. Note ID: {note_id}, Note Text: {note_text}, Added Tags: {tags}")
        print("~" * 80)

# A way of allowing the user to terminate the function without using <control> + <c>
def confirm_exit():
    confirm = input("Press Enter again to confirm exit, or any other key to continue: ").strip()
    if confirm == '':
        print("Exiting...")
        return True
    return False

# Interprets user input on index selection of specific notes accounting for ranges and discrete values
def parse_indices(input_str, total_length):
    indices = []
    parts = input_str.split(',')
    for part in parts:
        if ':' in part:
            start, end = part.split(':')
            start = int(start) - 1
            end = int(end)
            indices.extend(range(start, end))
        else:
            indices.append(int(part) - 1)
    indices = list(set(indices))  # Remove duplicates
    if any(i < 0 or i >= total_length for i in indices):
        raise ValueError("One or more indices are out of range.")
    return indices

def main():
    # Looks for usable files in the directory that doc_comparison.py places its outputs
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    files = load_modification_files(output_dir)
    files = sorted(files)
    if not files:
        print("No modification files found.")
        return

    # Prints file names for selection and identifies if files were outputs of this program with "*"
    print("Select a modification file to process:")
    for idx, filename in enumerate(files):
        file_path = os.path.join(output_dir, filename)
        modifications = parse_modification_file(file_path)
        note_ids = set(mod['Note ID'] for mod in modifications)
        card_ids = set(mod['Card ID'] for mod in modifications)
        mark = "*" if "anki_modifications_output_rev" in filename else ""
        print(f"{idx+1:>3}. {filename} - {len(note_ids)} notes, {len(card_ids)} cards {mark}")

    print("\n* user revised list")

    # Gets users choice of valid file number from list
    while True:
        selected_file_idx = input("Enter the number of the file to process (or press <return> to exit): ").strip()
        if selected_file_idx == '':
            if confirm_exit():
                return
            continue
        try:
            selected_file_idx = int(selected_file_idx) - 1
            if selected_file_idx < 0 or selected_file_idx >= len(files):
                print("Invalid selection. Please try again.")
            else:
                break
        except ValueError:
            print("Invalid input. Please enter a valid number or press <return> to exit.")

    selected_file = files[selected_file_idx]
    selected_filepath = os.path.join(output_dir, selected_file)
    modifications = parse_modification_file(selected_filepath)
    header = list(modifications[0].keys()) if modifications else []

    # Gets the users desired modification
    print("")
    print("What would you like to do with the referenced notes and cards?")
    print("1. Change the text of a specific tag on a note")
    print("2. Remove a specific tag on a note")
    print("3. Add an additional tag on a note")
    print("4. Suspend cards")
    print("5. Unsuspend cards")
    print("")

    while True:
        action = input("Enter the number of the action (or press <return> to exit): ").strip()
        print("")
        if action == '':
            if confirm_exit():
                return
            continue
        try:
            action = int(action)
            if action not in range(1, 6):
                print("Invalid selection. Please try again.")
            else:
                break
        except ValueError:
            print("Invalid input. Please enter a valid number or press <return> to exit.")

    # Gets the user to choose between altering all notes or specific notes.
    while True:
        all_or_specific = input("What action would you like to take:\n\n1) Change ALL notes in the list\n2) Select specific notes to change\n\n(press <return> to exit)\n\nselection: ").strip().lower()
        print("")
        if all_or_specific == "1" or all_or_specific == '2':
            break
        if all_or_specific == "":
            if confirm_exit():
                return
    
    # Allows the user to identify the specific indicies that are to be changed
    selected_indices = []
    if all_or_specific == "2":
        while True:
            try:
                print("Select the notes to alter:")
                unique_modifications = []
                seen_note_ids = set()
                for mod in modifications:
                    if mod['Note ID'] not in seen_note_ids:
                        unique_modifications.append(mod)
                        seen_note_ids.add(mod['Note ID'])
                print_modifications(unique_modifications, selected_indices)
                selected_indices_input = input("Enter the indices of the notes to alter (comma-separated or range, e.g., 1,2,4:6, or press <return> to exit): ").strip()
                if selected_indices_input == '':
                    if confirm_exit():
                        return
                    continue
                selected_indices = parse_indices(selected_indices_input, len(unique_modifications))
                
                # Confirm the selection and allow modifications
                while True:
                    print("\nIs this the full list of notes you wish to modify?")
                    print_modifications(unique_modifications, selected_indices)

                    modify_selection = input("Enter 'y' to continue, add more notes, or enter the number of already added notes to remove them (or press <return> to exit): ").strip().lower()
                    if modify_selection == 'y':
                        break
                    elif modify_selection == '':
                        if confirm_exit():
                            return
                        continue
                    else:
                        additional_indices = parse_indices(modify_selection, len(unique_modifications))
                        # Allows for deselection of indicies
                        for idx in additional_indices:
                            if idx in selected_indices:
                                selected_indices.remove(idx)
                            else:
                                selected_indices.append(idx)

                break
            except ValueError as e:
                print(f"Invalid input: {e}. Please enter valid indices or ranges separated by commas or press <return> to exit.")
    else:
        unique_modifications = []
        seen_note_ids = set()
        for mod in modifications:
            if mod['Note ID'] not in seen_note_ids:
                unique_modifications.append(mod)
                seen_note_ids.add(mod['Note ID'])
        selected_indices = list(range(len(unique_modifications)))
    
    selected_note_ids = [unique_modifications[i]['Note ID'] for i in selected_indices]

    # 1. Change the text of a specific tag on a note
    if action == 1:
        print("Checking the tags in the selected notes...")
        all_tags = set()
        for note_id in selected_note_ids:
            mods = [mod for mod in modifications if mod['Note ID'] == note_id]
            for mod in mods:
                current_tags = mod['Added Tags']
                if current_tags:
                    all_tags.update(current_tags)

        # Looks at the .csv NOT Anki to enumerate tags
        if len(all_tags) == 0:
            print("No tag(s) in the selected notes.\nExiting...")
            return
        # Automatically proceeds with the single tag in cases where only one is noted
        elif len(all_tags) == 1:
            old_tag = next(iter(all_tags))
            print(f"'{old_tag}' will be replaced on these notes.")
            while True:
                tag_to_add = input("\nEnter the new tag or press <return> to exit: ").strip()
                if tag_to_add == '':
                    if confirm_exit():
                        return
                    else:
                        continue
                confirm = input(f"\nDo you want to change the tag '{old_tag}' to '{tag_to_add}' on all selected notes? (y/n): ").strip().lower()
                if confirm == 'y':
                    for note_id in selected_note_ids:
                        remove_note_tags(note_id, [old_tag])
                        full_tags = get_note_tags(note_id)
                        if tag_to_add not in full_tags:
                            update_note_tags(note_id, [tag_to_add])
                            for mod in modifications:
                                if mod['Note ID'] == note_id:
                                    mod['Added Tags'] = [tag_to_add]
                    break
                else:
                    continue
        # If multiple tags are noted in the .csv the user can choose which one they want to change
        else:
            print("Tags in the selected notes:")
            all_tags = list(all_tags)
            while True:
                for idx, tag in enumerate(all_tags):
                    print(f"{idx+1}. {tag}")
                try:
                    selected_tag_idx = int(input("\nEnter the number of the tag to change or press <return> to exit: ").strip()) - 1
                except:
                    if selected_tag_idx == '':
                        if confirm_exit():
                            return
                    print("Invalid input...")
                    continue
                old_tag = all_tags[selected_tag_idx]
                tag_to_add = input("\nEnter the new tag: ").strip()
                confirm = input(f"\nDo you want to change the tag '{old_tag}' to '{tag_to_add}' on all selected notes? (y/n): ").strip().lower()
                if confirm == 'y':
                    for note_id in selected_note_ids:
                        remove_note_tags(note_id, [old_tag])
                        full_tags = get_note_tags(note_id)
                        if tag_to_add not in full_tags:
                            update_note_tags(note_id, [tag_to_add])
                            for mod in modifications:
                                if mod['Note ID'] == note_id:
                                    mod['Added Tags'] = [tag_to_add]
                    break
                else:
                    continue

    # 2. Remove a specific tag on a note
    elif action == 2:
        print("Checking the tags in the selected notes...")
        all_tags = set()
        for note_id in selected_note_ids:
            mods = [mod for mod in modifications if mod['Note ID'] == note_id]
            for mod in mods:
                current_tags = mod['Added Tags']
                if current_tags:
                    all_tags.update(current_tags)

        # Looks at the .csv NOT Anki to enumerate tags
        if len(all_tags) == 0:
            print("No tag(s) in the selected notes.\nExiting...")
            return
        
        # Automatically proceeds with the single tag in cases where only one is noted
        elif len(all_tags) == 1:
            tag_to_remove = next(iter(all_tags))
            confirm = input(f"\nDo you want to remove the tag '{tag_to_remove}' from all selected notes? (y/n): ").strip().lower()
            if confirm == 'y':
                for note_id in selected_note_ids:
                    remove_note_tags(note_id, [tag_to_remove])
                    for mod in modifications:
                        if mod['Note ID'] == note_id:
                            mod['Added Tags'] = []
            else:
                print("Exiting...")

        # If multiple tags are noted in the .csv the user can choose which one they want to delete
        else:
            print("Tags in the selected notes:")
            all_tags = list(all_tags)
            while True:
                for idx, tag in enumerate(all_tags):
                    print(f"{idx+1}. {tag}")
                try:
                    selected_tag_idx = int(input("\nEnter the number of the tag to remove or press <return> to exit: ").strip()) - 1
                except:
                    if selected_tag_idx == '':
                        if confirm_exit():
                            return
                    print("Invalid input...")
                    continue
                tag_to_remove = all_tags[selected_tag_idx]
                confirm = input(f"\nDo you want to remove the tag '{tag_to_remove}' from all selected notes? (y/n): ").strip().lower()
                if confirm == 'y':
                    for note_id in selected_note_ids:
                        remove_note_tags(note_id, [tag_to_remove])
                        for mod in modifications:
                            if mod['Note ID'] == note_id:
                                current_tags = mod['Added Tags']
                                current_tags.remove(tag_to_remove)
                                mod['Added Tags'] = current_tags
                    break
                else:
                    continue

    # 3. Add an additional tag on a note
    elif action == 3:
        while True:
            tag_to_add = input("\nEnter the tag to add (or press <return> to exit): ").strip()
            if tag_to_add == '':
                if confirm_exit():
                    return
                else:
                    continue
            confirm = input(f"\nDo you want to add the tag '{tag_to_add}' to all selected notes? (y/n): ").strip().lower()
            if confirm == 'y':
                for note_id in selected_note_ids:
                    current_tags = get_note_tags(note_id)
                    if tag_to_add not in current_tags:
                        update_note_tags(note_id, [tag_to_add])
                        for mod in modifications:
                            if mod['Note ID'] == note_id:
                                mod['Added Tags'].append(tag_to_add)
                break
            else:
                continue

    # 4. Suspend cards
    elif action == 4:
        confirm = input("\nDo you want to suspend all selected notes? (y/n): ").strip().lower()
        if confirm == 'y':
            set_card_suspend(selected_note_ids, True)
            for note_id in selected_note_ids:
                for mod in modifications:
                    if mod['Note ID'] == note_id:
                        mod['Card Status'] = 'suspended'
            print("Selected cards were suspended.")
        else:
            print("No changes were made.")

    # 5. Unsuspend cards
    elif action == 5:
        confirm = input("\nDo you want to unsuspend all selected notes? (y/n): ").strip().lower()
        if confirm == 'y':
            set_card_suspend(selected_note_ids, False)
            for note_id in selected_note_ids:
                for mod in modifications:
                    if mod['Note ID'] == note_id:
                        mod['Card Status'] = 'unsuspended'
            print("Selected cards were unsuspended.")
        else:
            print("No changes were made.")
    if confirm == 'y':
        generate_output_file(modifications, header)

if __name__ == "__main__":
    main()
