# Anki Automation Version 1.0
This project leverages a sentence similarity LLM to compare user provided text to cloze-formatted Anki notes and allows users to automatically tag and/or unlock relevant cards.

These programs are grounded in the idea that aligning widely utilized Anki resources with the curricula of individual medical schools is prohibitively time consuming. The hope is that successive revisions of this resource will create an increasingly robust tool to automate this process and save students substantial amounts of time and energy.

This document will explain how to set up your computer to run these programs as clearly as possible. It it geared toward people with a mederate understanding of computer file structures and Anki.

## Step 0 Please Read

These programs uses the **AnkiConnect API** to interact with the Anki application on your computer. Big thanks to Alex Yatskov whose development of this API made these programs possible.

AnkiConnect is available on AnkiWeb here: https://ankiweb.net/shared/info/2055492159 

AnkiConnect's detailed documentation can be found here: https://foosoft.net/projects/anki-connect/

In order to connect to Anki via API, Anki needs to be running on your computer. I would recommend **NOT reviewing cards** as well as **NOT making any changes in the Anki user interface** while the program is running.

I recommend:
1) syncing your Anki with AnkiWeb prior to running the program
2) **turning OFF automatic synchronization**
3) familiarizing yourself with how to **force changes in one direction (Download from AnkiWeb)**.

These safeguards will prevent unwanted changes while you are learning to use the program.

These programs are desinged to use the latest version of python which as of this writing is version 3.12.4.

At some point during this installation your Mac may prompt and require you to **install Xcode developer tools**.

If you need to install python on your computer you can download the latest version here: https://www.python.org/downloads/

This process can be frustrating but searching any errors that the terminal displays will provide detailed troubleshooting options.

## Step 1 Cloning This Repository

1) On your Mac open the terminal or the equivalent on a PC. 

2) Choose a folder on your computer where you want to interact with these programs. Open this folder in the terminal by opening a finder window, selecting the "View" dropdown menu on the top left of your screen and clicking "Show Path Bar". The path bar is now visible on the bottom of all finder windows. Right click and select "Open in Terminal".

Note that if there are spaces in any of the folder names on this path it may cause issues and I would recommend replacing any spaces with underscores "_" to avoid potential issues.

4) Paste the following into the terminal and press <return>

`git clone https://github.com/astarzinski/anki_automation_v1.git`

The repository has now been cloned to the folder you specified. Stay in the terminal for the next step.

## Step 2 Installing Required Dependencies (python add-ons)

4) Enter `cd anki_automation_v1` into the terminal and press <return>.

5) Enter `pip3 install -r requirements.txt` and press <return>. The required python libraries will now be installed.

Your environment is now ready to run the programs!

## Step 3 Running The Programs

### Embedding Your Anki Deck:

The program "anki_deck_embedding.py" needs to only be run once which is good because it is very computationally intensive and takes around 12 minutes for 28,000 notes on an M1 Mac with 16 GB of RAM.

6) To run this program make sure Anki is running and enter `python3 anki_deck_embedding.py` into the terminal.

7) You will be asked to select the deck you wish to process. Enter the number of the deck in the displayed menu.

If you often write new cards or make changes to the cloze text of cards you may want to periodically rerun this program as it will not incorporate any of the changes you make to the text of your cards unless you do. If you have an existing Anki deck embedding you will be asked to confirm that you want to create a new one.

### Embedding Text Documents and Modifying Relevant Notes/Cards:

The program "doc_comparison.py" is run for every document you want to compare against your deck.

8) Enter `python3 doc_comparison.py` into the terminal and you will be prompted to make sure that the document you want to use is placed in the "input" folder which itself is in the "anki_automation_v1" folder.

You can place as many documents as you like into the 'input' folder and they will be selectable when running the program.

## Step 4 Detailed Description of Note/Card Changes.

When you compare a selected document against your Anki deck you will see a color coded list of notes with the most related notes having the lowest indices and highest scores. you can select up to 1000 notes but in reality you will likely not want to tag more than 100. You will have to scroll up in the terminal to see the entire list. Each color red to purple has decreasing relatedness to the document and wider intervals between cards.

9) You will **enter an integer value** for the index that you want to limit how many notes you tag (or note derrived cards you unlock or both).

10) If you have chosen to tag the indetified notes you will be prompted to enter a value for this tag. **Do NOT include any spaces**.

A summary will populate at the end of the program.

You can now confirm that the desired changes were made in you anki deck.

Finally, a summary document will appear in the "output" folder where you can see a detailed list of all of the note and card ID's that were modified in case you want to further curate the changes that were made to your Anki deck.

## Step 5 Intermittent Access to the Programs via Terminal.

For subsequent use of either program use the following in a fresh terminal window:

```
cd path/to/anki_automation_v1
python3 doc_comparison.py
```
OR
```
cd path/to/anki_automation_v1
python3 anki_deck_embedding.py
```
