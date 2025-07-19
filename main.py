"""
Pokemon Showdown Automated Battle Bot - Main Module

This module provides a complete automated battle bot for Pokemon Showdown using Selenium
WebDriver for web automation and Claude AI for intelligent battle decisions. The bot can:

- Automatically log into Pokemon Showdown
- Import and manage Pokemon teams
- Parse battle state and opponent information
- Make intelligent battle decisions using AI
- Execute moves and handle battle flow
- Track battle logs and reasoning

Author: LLM Pokemon Showdown Project
Dependencies: selenium, undetected-chromedriver, beautifulsoup4, pydantic, python-dotenv
Usage: Run main() to start automated battling
"""

import json
import os
import random
import re
import time
from typing import Literal, Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import undetected_chromedriver as uc

from ace_trainer import AceTrainer
from type_chart import determine_effectiveness


class Pokemon(BaseModel):
    """
    Represents a Pokemon with all its battle-relevant attributes.
    
    This model captures everything needed to make informed battle decisions,
    including stats, typing, status conditions, and available moves.
    """
    name: str
    hp: float = Field(description="The current HP percentage out of 100 of the Pokémon")
    type1: Literal[
        "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison", 
        "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", 
        "Steel", "Fairy", "Stellar", "Not Specified"
    ]
    type2: Literal[
        "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison", 
        "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", 
        "Steel", "Fairy", "Stellar", "Not Specified"
    ]
    tera_type: Literal[
        "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison", 
        "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", 
        "Steel", "Fairy", "Stellar", "Not Specified"
    ] = "Not Specified"
    ability: list[str]
    moves: list[str]
    item: str
    speed_min: int
    speed_max: int
    status: Literal["none", "Burn", "Poison", "Paralysis", "Sleep", "Freeze"]
    fainted: bool


class Team(BaseModel):
    """
    Represents a complete Pokemon team with active Pokemon and team roster.
    
    Contains the currently active Pokemon, the full team roster, and mapping
    data needed for web automation interactions.
    """
    active_pokemon: Optional[Pokemon]
    pokemon: list[Pokemon]
    pokemon_dict: dict[str, str]  # Maps Pokemon names to their data-tooltip values
    

class Move(BaseModel):
    """
    Represents a Pokemon move with all relevant battle information.
    
    Includes move metadata needed for both battle decisions and web automation.
    """
    name: str
    pp_left: int  # Remaining Power Points for this move
    value: str = Field(description="Used to help the scraper click on the move.")
    key: str = Field(description="Used to help the scraper identify the move.")
    type: Literal[
        "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison", 
        "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", 
        "Steel", "Fairy", "Stellar", "Not Specified"
    ]
    

class BattleLogEntry(BaseModel):
    """
    Represents a single turn's worth of battle log information.
    
    Captures all actions that occurred during a specific turn for AI analysis.
    """
    turn: int
    actions_in_order: list[str]  # All actions that happened this turn, in sequence
    

class BattleMove(BaseModel):
    """
    Represents a battle decision to be executed.
    
    This is the structured output from the AI trainer that gets converted
    into actual web interactions.
    """
    action: Literal[
        "Move 1", "Move 2", "Move 3", "Move 4", 
        "Switch 1", "Switch 2", "Switch 3", "Switch 4", "Switch 5", "Switch 6"
    ]
    terastallize: bool
    reason: str = Field(description="Less than 50 word explanation on why this is a good decision.")


class ShowdownBot:
    """
    Main bot class that handles all Pokemon Showdown automation.
    
    This class orchestrates the entire battle process from login to battle execution,
    including team management, battle state parsing, AI decision making, and move execution.
    """
    
    def __init__(self, print_mode: bool = True):
        """
        Initialize the Showdown bot with necessary components.
        
        Args:
            print_mode: Whether to enable verbose logging output
        """
        # Load environment variables for credentials
        load_dotenv()
        self.print_mode = print_mode
        
        # Initialize AI trainer for battle decisions
        self.ace_trainer = AceTrainer(BattleMove)
        
        # Set up Chrome WebDriver for web automation
        self.setup_driver()
        
        # Load move classification data for type effectiveness calculations
        self.move_classifier = json.load(open("attack_dict.json"))
        
        # Track the last reasoning for context in subsequent decisions
        self.last_reasoning = ""
        
    def close(self):
        """
        Safely close the WebDriver and clean up resources.
        
        This method should be called when the bot is finished to prevent
        resource leaks and zombie browser processes.
        """
        if hasattr(self, 'driver'):
            self.driver.quit()
            self.log("WebDriver closed successfully")
        
    def setup_driver(self):
        """
        Initialize and configure the Chrome WebDriver for Pokemon Showdown.
        
        Sets up an undetected Chrome instance with optimized settings for
        web automation and Pokemon Showdown compatibility.
        """
        # Configure Chrome options for optimal performance and stealth
        chrome_options = uc.ChromeOptions()
        chrome_options.page_load_strategy = "eager"  # Don't wait for all resources
        chrome_options.add_argument("--window-size=1920,1080")  # Standard resolution
        chrome_options.add_argument("--no-sandbox")  # Required for some environments
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
        chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
        chrome_options.add_argument("--mute-audio")  # Silence browser audio
        
        # Initialize undetected Chrome WebDriver
        if os.getenv("CHROME_PATH") is None:
            raise ValueError("CHROME_PATH environment variable is not set")
        
        self.driver = uc.Chrome(
            options=chrome_options,
            browser_executable_path=os.getenv("CHROME_PATH"),
        )
        
        # Set reasonable timeout for page loads
        self.driver.set_page_load_timeout(30)
        
    def parse_pokemon_tooltip(self, tooltip_html_content, is_opponent_pokemon=True):
        """
        Parse Pokemon tooltip HTML to extract comprehensive Pokemon information.
        
        This method extracts all available information about a Pokemon from the
        hover tooltip, including stats, typing, status, moves, and items.
        
        Args:
            tooltip_html_content: Raw HTML content from the Pokemon tooltip
            is_opponent_pokemon: True if parsing opponent's Pokemon, False for player's
            
        Returns:
            dict: Comprehensive Pokemon data including all battle-relevant attributes
        """
        # Parse HTML content with BeautifulSoup
        tooltip_soup = BeautifulSoup(tooltip_html_content, 'html.parser')

        # Map Showdown status abbreviations to full names
        status_abbreviation_map = {
            "BRN": "Burn",
            "PSN": "Poison", 
            "TOX": "Poison",  # Badly poisoned also maps to Poison
            "PAR": "Paralysis",
            "SLP": "Sleep",
            "FRZ": "Freeze"
        }

        # Extract Pokemon typing information
        pokemon_types = []
        tera_type = "Not Specified"
        
        # Find main type icons
        main_type_container = tooltip_soup.select_one('.textaligned-typeicons')
        if main_type_container:
            type_images = main_type_container.select('img')
            pokemon_types = [img.get('alt') for img in type_images if img.get('alt')]
        
        # Find Tera type if mentioned
        tera_type_mention = tooltip_soup.find(string=lambda text: text and "Tera Type:" in text)
        if tera_type_mention:
            tera_parent_element = tera_type_mention.parent
            tera_type_container = tera_parent_element.find_next('span', class_='textaligned-typeicons')
            if tera_type_container:
                tera_type_image = tera_type_container.find('img')
                if tera_type_image and tera_type_image.get('alt'):
                    tera_type = tera_type_image.get('alt')
        
        # Assign primary and secondary types
        primary_type = pokemon_types[0] if len(pokemon_types) >= 1 else "Not Specified"
        secondary_type = pokemon_types[1] if len(pokemon_types) >= 2 else "Not Specified"

        # Extract HP and status information
        current_hp_percentage = 100.0  # Default to full HP
        is_pokemon_fainted = False
        status_condition = "none"
        
        # Search through all paragraph tags for HP information
        for paragraph_tag in tooltip_soup.find_all("p"):
            small_tag = paragraph_tag.find("small")
            if small_tag and "HP:" in small_tag.text:
                paragraph_text_lower = paragraph_tag.get_text().lower()
                
                # Check if Pokemon is fainted
                if "(fainted)" in paragraph_text_lower:
                    is_pokemon_fainted = True
                    current_hp_percentage = 0.0
                else:
                    # Extract HP percentage
                    hp_percentage_match = re.search(r'(\d+\.?\d*)%', paragraph_tag.get_text())
                    if hp_percentage_match:
                        current_hp_percentage = float(hp_percentage_match.group(1))

                # Extract status condition
                status_element = paragraph_tag.find("span", class_="status")
                if status_element:
                    showdown_status_code = status_element.get_text().strip().upper()
                    if showdown_status_code in status_abbreviation_map:
                        status_condition = status_abbreviation_map[showdown_status_code]

                break  # Found HP info, no need to continue searching

        # Extract ability information
        pokemon_abilities = []
        for paragraph_tag in tooltip_soup.find_all("p"):
            small_tag = paragraph_tag.find("small")
            if small_tag:
                small_text_lower = small_tag.text.lower()
                if "ability:" in small_text_lower or "possible abilities:" in small_text_lower:
                    ability_text = paragraph_tag.get_text(separator=" ").strip()
                    # Remove the "Ability:" or "Possible abilities:" prefix
                    ability_text = re.sub(r'^(.*abilities?:)', '', ability_text, flags=re.IGNORECASE).strip()
                    pokemon_abilities = [ability.strip() for ability in ability_text.split(',') if ability.strip()]
                    break

        # Extract speed stat information
        speed_stat_minimum, speed_stat_maximum = 0, 0
        
        if is_opponent_pokemon:
            # For opponents, speed is shown as a range
            for paragraph_tag in tooltip_soup.find_all("p"):
                small_tag = paragraph_tag.find("small")
                if small_tag and "Spe" in small_tag.text:
                    speed_range_match = re.search(r'(\d+)\s*to\s*(\d+)', paragraph_tag.get_text())
                    if speed_range_match:
                        speed_stat_minimum = int(speed_range_match.group(1))
                        speed_stat_maximum = int(speed_range_match.group(2))
                    break
        else:
            # For player's Pokemon, speed is shown as exact value
            for paragraph_tag in tooltip_soup.find_all("p"):
                if "Spe" in paragraph_tag.get_text():
                    speed_exact_match = re.search(r'Spe\s*[^0-9]*(\d+)', paragraph_tag.get_text())
                    if speed_exact_match:
                        exact_speed_value = int(speed_exact_match.group(1))
                        speed_stat_minimum = exact_speed_value
                        speed_stat_maximum = exact_speed_value
                    break

        # Extract revealed moves information
        revealed_moves = []
        tooltip_move_sections = tooltip_soup.select('p.tooltip-section')
        for move_section in tooltip_move_sections:
            section_lines = move_section.get_text(separator="\n").split("\n")
            for line in section_lines:
                if line.strip().startswith("•"):
                    # Extract move name, removing bullet point and any additional info
                    move_text = line.replace("•", "", 1).strip()
                    move_text = re.sub(r'\(.*\)', '', move_text).strip()  # Remove parenthetical info
                    revealed_moves.append(move_text)

        # Extract item information
        pokemon_item = "Unknown" if is_opponent_pokemon else "No Item"
        for paragraph_tag in tooltip_soup.find_all("p"):
            small_tag = paragraph_tag.find("small")
            if small_tag and "Item:" in small_tag.text:
                item_text = paragraph_tag.get_text(separator=" ").strip()
                # Remove "Item:" prefix
                item_text = re.sub(r'^(.*Item:)', '', item_text, flags=re.IGNORECASE).strip()
                if item_text:
                    pokemon_item = item_text
                break

        # Return comprehensive Pokemon data
        return {
            "type1": primary_type,
            "type2": secondary_type,
            "tera_type": tera_type,
            "hp": current_hp_percentage,
            "fainted": is_pokemon_fainted,
            "status": status_condition,
            "ability": pokemon_abilities,
            "speed_min": speed_stat_minimum,
            "speed_max": speed_stat_maximum,
            "moves": revealed_moves,
            "item": pokemon_item
        }

    def get_opponent_pokemon(self):
        """
        Parse and extract the opponent's Pokemon team from the battle interface.
        
        This method scrapes the opponent's Pokemon information by hovering over
        their Pokemon icons to reveal tooltips with stats, typing, and other data.
        
        Returns:
            tuple: (active_pokemon, team_list) where active_pokemon is the currently
                   active Pokemon object and team_list contains all opponent Pokemon
        """
        try:
            # Find the opponent's trainer container on the far side
            opponent_trainer_container = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.trainer.trainer-far"))
            )
            
            # Get all Pokemon icon elements for the opponent
            opponent_pokemon_icons = opponent_trainer_container.find_elements(
                By.CSS_SELECTOR, "span.picon"
            )
            
            currently_active_pokemon = None
            opponent_team_roster = []
            
            # Process each Pokemon icon to extract information
            for pokemon_icon in opponent_pokemon_icons:
                # Get the aria-label which contains Pokemon name and status
                pokemon_aria_label = pokemon_icon.get_attribute("aria-label")
                
                # Skip fainted Pokemon (they don't provide useful battle info)
                if pokemon_aria_label.endswith("(fainted)"):
                    continue
                
                # Hover over the icon to trigger the tooltip
                hover_action = ActionChains(self.driver)
                hover_action.move_to_element(pokemon_icon).perform()
                
                # Wait for the tooltip to appear and capture its content
                pokemon_tooltip = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "tooltipwrapper"))
                )
                tooltip_html_content = pokemon_tooltip.get_attribute("innerHTML")
                
                # Extract Pokemon name from aria-label (before any status indicators)
                if pokemon_aria_label:
                    pokemon_name = pokemon_aria_label.split(" (")[0]
                    
                    # Parse the tooltip to get comprehensive Pokemon data
                    pokemon_data = self.parse_pokemon_tooltip(
                        tooltip_html_content, 
                        is_opponent_pokemon=True
                    )
                    pokemon_data["name"] = pokemon_name
                    
                    # Create Pokemon object with all extracted data
                    parsed_pokemon = Pokemon(
                        name=pokemon_data["name"],
                        hp=pokemon_data["hp"],
                        type1=pokemon_data["type1"],
                        type2=pokemon_data["type2"],
                        tera_type=pokemon_data["tera_type"],
                        ability=pokemon_data["ability"],
                        moves=pokemon_data["moves"],
                        item=pokemon_data["item"],
                        speed_min=pokemon_data["speed_min"],
                        speed_max=pokemon_data["speed_max"],
                        status=pokemon_data["status"],
                        fainted=pokemon_data["fainted"]
                    )
                    
                    # Skip if this Pokemon is fainted (double-check)
                    if pokemon_data["fainted"]:
                        continue
                    
                    # Determine if this is the active Pokemon
                    if "(active)" in pokemon_aria_label:
                        currently_active_pokemon = parsed_pokemon
                    
                    # Add to the team roster
                    opponent_team_roster.append(parsed_pokemon)
                    
                # Small delay to avoid overwhelming the interface
                time.sleep(random.uniform(0.1, 0.2))
            
            return currently_active_pokemon, opponent_team_roster
            
        except Exception as parsing_error:
            self.log(f"Error getting opponent's Pokémon: {parsing_error}")
            return None, []
    
    def make_move(self, battle_controls) -> Optional[BattleMove]:
        """
        Generate and return an AI-powered battle decision based on current battle state.
        
        This method analyzes the current battle situation, including team states,
        opponent information, and battle history to make an optimal move decision
        using the AI trainer.
        
        Args:
            battle_controls: Dict containing current battle state including moves,
                           switches, team info, and battle start status
                           
        Returns:
            Optional[BattleMove]: AI-generated battle decision, or None if error occurs
        """
        ai_decision = None
        
        # Get current opponent information
        opponent_active_pokemon, opponent_full_team = self.get_opponent_pokemon()
        
        # Handle battle start scenario (lead Pokemon selection)
        if battle_controls["battle_start"]:
            battle_situation_prompt = "The battle has started!"
            battle_situation_prompt += f"\n\nThis is the opponents team: {opponent_full_team}"
            battle_situation_prompt += f"\n\nThis is your team: {battle_controls['team']}"
            battle_situation_prompt += "\nYou will be provided with a list of switches in the format: Switch X: Pokemon Name"
            battle_situation_prompt += "\nRespond with `Switch X` where X is the number of the pokemon you want to switch into."
            battle_situation_prompt += f"\nChoose who you want to switch into:"
            
            # List all available Pokemon to switch into
            for switch_identifier, pokemon_name in battle_controls["available_switches"].items():
                battle_situation_prompt += f"\n\n{switch_identifier}: {pokemon_name}"
            
            try:
                # Get AI decision for lead Pokemon
                ai_decision, reasoning_explanation = self.ace_trainer.generate_battle_moves(battle_situation_prompt)
                self.last_reasoning = reasoning_explanation
                
            except Exception as ai_error:
                print(f"Error generating battle moves: {ai_error}")
                input("Error generating battle moves. Please make a decision manually, then hit enter.")
            
            return ai_decision
        
        # Handle mid-battle decision making
        # First, get battle history for context
        complete_battle_log = self.get_battle_log()
        battle_situation_prompt = "To explain the battle situation, here is the battle log so far: "
        
        # Add each turn's actions to the prompt
        for log_entry in complete_battle_log:
            battle_situation_prompt += f"\n{log_entry.turn}: {log_entry.actions_in_order}"
        
        # Add current team and Pokemon information
        battle_situation_prompt += f"\n\nThis is the opponents team: {opponent_full_team}"
        battle_situation_prompt += f"\n\nThis is the opponents active pokemon: {opponent_active_pokemon}"
        battle_situation_prompt += f"\n\nThis is your team: {battle_controls['team']}"
        battle_situation_prompt += f"\n\nThis is your active pokemon: {battle_controls['active_pokemon']}"
        
        # Provide instructions for response format
        battle_situation_prompt += "\nYou will be provided with a list of moves in the format: `Move X: Move Name` and a list of switches in the format: `Switch X: Pokemon Name`"
        battle_situation_prompt += "\nChoose what option you want to select out of those available."
        
        # Add Terastallize option if available
        if battle_controls["terastallize"]["available"]:
            terastallize_type = battle_controls['terastallize']['type']
            battle_situation_prompt += f"\nAlso, indicate whether you want to terastallize into a {terastallize_type} type."

        # List all available moves with type effectiveness information
        battle_situation_prompt += "\n\nAvailable moves:"
        
        for move_identifier, move_data in battle_controls["moves_dict"].items():
            move_description = f"\n{move_identifier}: {move_data.name}"
            
            # Add type effectiveness information for attacking moves
            if opponent_active_pokemon and move_data.name in self.move_classifier["attack"]:
                type_effectiveness = determine_effectiveness(
                    move_data.type, 
                    opponent_active_pokemon.type1, 
                    opponent_active_pokemon.type2
                )
                move_description += f" ({type_effectiveness})"
            else:
                move_description += f" (Status move)"
            
            battle_situation_prompt += move_description
            
        # List all available Pokemon switches
        battle_situation_prompt += "\n\nAvailable switches:"
        for switch_identifier, pokemon_name in battle_controls["available_switches"].items():
            battle_situation_prompt += f"\n{switch_identifier}: {pokemon_name}"
        
        # Add context from previous decision if available
        if self.last_reasoning:
            battle_situation_prompt += f"\n\nThe last action you took and the reasoning you provided: {self.last_reasoning}"
        
        try:
            # Get AI decision for the current battle situation
            ai_decision, reasoning_explanation = self.ace_trainer.generate_battle_moves(battle_situation_prompt)
            self.last_reasoning = reasoning_explanation
            
        except Exception as ai_error:
            print(f"Error generating battle moves: {ai_error}")
            input("Error generating battle moves. Please make a decision manually, then hit enter.")
        
        return ai_decision
        
    def terastallize(self):
        """
        Activate Terastallization by clicking the terastallize checkbox.
        
        This method finds and clicks the terastallize checkbox in the battle interface
        if it's available and not already selected.
        
        Returns:
            bool: True if terastallization was successful or already active, False on error
        """
        try:    
            # Find the terastallize checkbox element
            terastallize_checkbox = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='terastallize']"))
            )
            
            # Click the checkbox if it's not already selected
            if not terastallize_checkbox.is_selected():
                terastallize_checkbox.click()
                self.log("Terastallization activated successfully")
                return True
            else:
                self.log("Terastallize checkbox was already selected")
                return True
                
        except Exception as terastallize_error:
            self.log(f"Error activating terastallization: {terastallize_error}")
            return False
        
    def get_player_team(self):
        """
        Parse and extract the player's Pokemon team from the battle interface.
        
        This method scrapes the player's Pokemon information from the switch menu
        by hovering over Pokemon buttons to reveal detailed tooltips.
        
        Returns:
            Team: Team object containing active Pokemon, full roster, and tooltip mappings
        """
        try:
            # Find the switch menu containing player's Pokemon
            pokemon_switch_menu = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.switchmenu"))
            )
            
            # Get all Pokemon switch buttons
            pokemon_switch_buttons = pokemon_switch_menu.find_elements(
                By.CSS_SELECTOR, "button[data-tooltip^='switchpokemon']"
            )
            
            player_pokemon_roster = []
            currently_active_pokemon = None
            pokemon_tooltip_mapping = {}  # Maps Pokemon names to data-tooltip values
            
            # Process each Pokemon button to extract information
            for pokemon_button in pokemon_switch_buttons:
                # Get button attributes for Pokemon identification
                pokemon_button_value = pokemon_button.get_attribute("value")
                pokemon_data_tooltip = pokemon_button.get_attribute("data-tooltip")
                
                # Skip disabled buttons (usually for fainted or unavailable Pokemon)
                button_classes = pokemon_button.get_attribute("class").split()
                is_button_disabled = "disabled" in button_classes
                if is_button_disabled:
                    continue
                
                # Parse button value to determine Pokemon status
                if "," in pokemon_button_value:
                    pokemon_initial_name, pokemon_status = pokemon_button_value.split(",", 1)
                    is_currently_active = pokemon_status == "active"
                    is_pokemon_fainted = pokemon_status == "fainted"
                else:
                    pokemon_initial_name = pokemon_button_value
                    is_currently_active = False
                    is_pokemon_fainted = False
                
                # Hover over button to trigger tooltip
                hover_action = ActionChains(self.driver)
                hover_action.move_to_element(pokemon_button).perform()
                
                # Wait for tooltip to appear and capture content
                pokemon_tooltip = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "tooltipwrapper"))
                )
                tooltip_html_content = pokemon_tooltip.get_attribute("innerHTML")
                
                # Parse tooltip to extract comprehensive Pokemon data
                pokemon_data = self.parse_pokemon_tooltip(
                    tooltip_html_content, 
                    is_opponent_pokemon=False
                )
                
                # Extract Pokemon name from tooltip title (more reliable than button value)
                tooltip_soup = BeautifulSoup(tooltip_html_content, 'html.parser')
                tooltip_title_element = tooltip_soup.find('h2')
                if tooltip_title_element:
                    pokemon_name = tooltip_title_element.get_text().strip()
                    # Clean up the name by removing level indicators and parenthetical info
                    pokemon_name = re.sub(r'\s*\([^)]*\)', '', pokemon_name)  # Remove (M), (F), etc.
                    pokemon_name = re.sub(r'\s*L\d+\s*', '', pokemon_name).strip()  # Remove level info
                else:   
                    pokemon_name = pokemon_initial_name
                
                # Set the cleaned name in Pokemon data
                pokemon_data["name"] = pokemon_name
                
                # Create Pokemon object with all extracted information
                team_pokemon = Pokemon(
                    name=pokemon_data["name"],
                    hp=pokemon_data["hp"],
                    type1=pokemon_data["type1"],
                    type2=pokemon_data["type2"],
                    tera_type=pokemon_data["tera_type"],
                    ability=pokemon_data["ability"],
                    moves=pokemon_data["moves"],
                    item=pokemon_data["item"],
                    speed_min=pokemon_data["speed_min"],
                    speed_max=pokemon_data["speed_max"],
                    status=pokemon_data["status"],
                    fainted=pokemon_data["fainted"] or is_pokemon_fainted
                )
                
                # Add to team roster
                player_pokemon_roster.append(team_pokemon)
                
                # Store tooltip mapping for later use in move execution
                if pokemon_data_tooltip:
                    pokemon_tooltip_mapping[pokemon_name] = pokemon_data_tooltip
                
                # Set as active Pokemon if currently in battle
                if is_currently_active:
                    currently_active_pokemon = team_pokemon
                
                # Small delay to avoid overwhelming the interface
                time.sleep(random.uniform(0.1, 0.2))
            
            # Create and return Team object
            player_team = Team(
                active_pokemon=currently_active_pokemon,
                pokemon=player_pokemon_roster,
                pokemon_dict=pokemon_tooltip_mapping
            )
            
            return player_team
            
        except Exception as team_parsing_error:
            self.log(f"Error getting player's Pokémon team: {team_parsing_error}")
            return None

    def get_controls(self, is_battle_start=False):
        """
        Extract and organize all available battle controls and current battle state.
        
        This method gathers comprehensive information about the current battle situation,
        including available moves, Pokemon switches, team status, and Terastallization options.
        
        Args:
            is_battle_start: True if this is the initial battle state, False for mid-battle
            
        Returns:
            dict: Comprehensive battle state including moves, switches, team info, and options
        """
        try:
            # Find the main battle controls container
            battle_controls_container = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.battle-controls"))
            )
            
            # Get current player team information
            current_player_team = self.get_player_team()
            
            # Extract available moves information
            available_moves_list = []
            available_moves_mapping = {}
            
            # Find all move buttons that are not disabled
            move_button_elements = battle_controls_container.find_elements(
                By.CSS_SELECTOR, "button.movebutton"
            )
            
            for move_index, move_button in enumerate(move_button_elements, 1):
                # Skip disabled moves (out of PP, choice-locked, etc.)
                if move_button.get_attribute("disabled"):
                    continue
                
                # Extract move information from button attributes
                move_name = move_button.get_attribute("data-move")
                move_tooltip_value = move_button.get_attribute("data-tooltip")
                
                # Extract PP (Power Points) information
                pp_display_element = move_button.find_element(By.CSS_SELECTOR, "small.pp")
                pp_text = pp_display_element.text
                
                try:
                    # Parse current PP from "X/Y" format
                    current_pp = int(pp_text.split('/')[0])
                except ValueError:
                    current_pp = 0  # Default if parsing fails
                
                # Extract move type information
                try:
                    move_type_element = move_button.find_element(By.CSS_SELECTOR, "small.type")
                    move_type = move_type_element.text
                except:
                    move_type = "Not Specified"  # Default if type not found
                
                # Create Move object with all extracted data
                move_data = Move(
                    name=move_name,
                    pp_left=current_pp,
                    value=move_tooltip_value,
                    key=f"Move {move_index}",
                    type=move_type
                )
                
                # Add to both list and mapping
                available_moves_list.append(move_data)
                available_moves_mapping[f"Move {move_index}"] = move_data
            
            # Extract Terastallization information
            terastallize_availability = {
                "available": False,
                "type": None
            }
            
            try:
                # Check if Terastallize checkbox exists
                terastallize_checkbox = battle_controls_container.find_element(
                    By.CSS_SELECTOR, "input[name='terastallize']"
                )
                if terastallize_checkbox:
                    terastallize_availability["available"] = True
                    
                    # Extract the Tera type from the associated image
                    tera_type_image = battle_controls_container.find_element(
                        By.CSS_SELECTOR, "label.megaevo img"
                    )
                    terastallize_availability["type"] = tera_type_image.get_attribute("alt")
                    
            except:
                # Terastallization not available this turn
                pass
            
            # Extract available Pokemon switches
            available_pokemon_switches = {}
            
            if current_player_team:
                # Create switch options for all non-fainted, non-active Pokemon
                for pokemon_index, team_pokemon in enumerate(current_player_team.pokemon):
                    # Skip fainted Pokemon
                    if team_pokemon.fainted:
                        continue
                    
                    # Skip currently active Pokemon (can't switch to already active Pokemon)
                    if (current_player_team.active_pokemon is not None and 
                        team_pokemon.name == current_player_team.active_pokemon.name):
                        continue
                    
                    # Add as available switch option
                    switch_key = f"Switch {pokemon_index + 1}"
                    available_pokemon_switches[switch_key] = team_pokemon.name
            
            # Compile comprehensive battle state information
            battle_state = {
                "active_pokemon": current_player_team.active_pokemon if current_player_team else None,
                "team": current_player_team,
                "moves": available_moves_list,
                "moves_dict": available_moves_mapping,
                "terastallize": terastallize_availability,
                "available_switches": available_pokemon_switches,
                "battle_start": is_battle_start
            }
            
            return battle_state
            
        except Exception as controls_error:
            self.log(f"Error getting battle controls: {controls_error}")
            return None
    
    def execute_move(self, battle_decision, current_battle_controls):
        """
        Execute the AI's battle decision by clicking the appropriate interface elements.
        
        This method translates the AI's decision into actual web interface interactions,
        handling both move selection and Pokemon switches.
        
        Args:
            battle_decision: BattleMove object containing the AI's decision
            current_battle_controls: Dict containing current battle state and available options
        """
        # Determine what type of action to execute
        if battle_decision.action.startswith("Switch"):
            # Handle Pokemon switch
            pokemon_to_switch_to = current_battle_controls["available_switches"][battle_decision.action]
            button_tooltip_identifier = current_battle_controls['team'].pokemon_dict[pokemon_to_switch_to]
            
        elif battle_decision.action.startswith("Move"):
            # Handle move selection
            selected_move = current_battle_controls["moves_dict"][battle_decision.action]
            button_tooltip_identifier = selected_move.value
            
            # Activate Terastallization if requested
            if battle_decision.terastallize:
                self.terastallize()

        # Find and click the appropriate button using its data-tooltip attribute
        target_button = self.driver.find_element(
            By.CSS_SELECTOR, 
            f"button[data-tooltip='{button_tooltip_identifier}']"
        )
        target_button.click()
    
    def click_timer(self):
        """
        Handle timer-related UI interactions (currently disabled).
        
        This method would normally click timer buttons to start battle timers,
        but it's currently commented out as it's not needed for basic functionality.
        """
        pass
        # Note: Timer functionality is disabled to avoid UI complications
        # 
        # Original implementation would:
        # 1. Click the timer button to open timer controls
        # 2. Start the battle timer
        # 
        # This can be re-enabled if timer management becomes necessary
             
    def is_battle_over(self):
        """
        Check if the current battle has ended.
        
        This method looks for the presence of battle end UI elements to determine
        if the battle has concluded (win, loss, or forfeit).
        
        Returns:
            bool: True if the battle has ended, False if still ongoing
        """
        try:    
            # Look for the main menu button that appears when battles end
            WebDriverWait(self.driver, 1).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.button[name='closeAndMainMenu']"))
            )
            return True
        except:
            # Button not found means battle is still ongoing
            return False
        
    def start_battle(self):
        """
        Execute the main battle loop from start to finish.
        
        This method handles the entire battle process including:
        - Initial timer setup
        - Lead Pokemon selection
        - Turn-by-turn decision making
        - Battle state monitoring
        """
        # Initialize timer (currently disabled)
        self.click_timer()
        
        # Small delay to let battle interface stabilize
        time.sleep(random.uniform(0.1, 0.2))
        
        # Handle lead Pokemon selection at battle start
        initial_battle_controls = self.get_controls(is_battle_start=True)
        lead_pokemon_decision = self.make_move(initial_battle_controls)
        if lead_pokemon_decision:
            self.execute_move(lead_pokemon_decision, initial_battle_controls)
        
        # Main battle loop - continue until battle ends
        while not self.is_battle_over():
            # Wait for opponent to make their move
            wait_start_time = time.time()
            while self.waiting_for_opponent():
                # Safety timeout to prevent infinite waiting
                if time.time() - wait_start_time > 150:  # 2.5 minutes
                    self.log("Timeout waiting for opponent - something may be broken")
                    break
                self.log("Waiting for opponent...")
                time.sleep(random.uniform(3, 5))
            
            # Get current battle state and make our move
            current_battle_controls = self.get_controls()
            ai_battle_decision = self.make_move(current_battle_controls)
            if ai_battle_decision:
                self.execute_move(ai_battle_decision, current_battle_controls)
            
            # Brief pause between actions to avoid overwhelming the interface
            time.sleep(random.uniform(0.3, 1))
    
    def waiting_for_opponent(self):
        """
        Check if the battle is currently waiting for the opponent to make a move.
        
        This method also handles UI interactions like skipping to the end of
        animations to speed up battle processing.
        
        Returns:
            bool: True if waiting for opponent, False if it's our turn
        """
        try:
            # Try to click "Go to End" button to skip animations
            try:
                skip_to_end_button = WebDriverWait(self.driver, 1).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[name='goToEnd']"))
                )
                skip_to_end_button.click()
                time.sleep(0.5)
            except:
                # No skip button available, continue normally
                pass
            
            # Check if battle controls are present
            battle_controls_element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.battle-controls"))
            )
            
            # Look for "Waiting for opponent" text in the battle controls
            _ = battle_controls_element.find_element(
                By.XPATH, ".//*[contains(text(), 'Waiting for opponent')]"
            )
            self.log("Currently waiting for opponent...")
            return True
            
        except:
            # No "waiting for opponent" text found - it's our turn
            return False
    
    def get_battle_log(self):
        """
        Parse and extract the complete battle log from the battle interface.
        
        This method scrapes the battle log HTML to extract turn-by-turn actions
        that occurred during the battle, providing context for AI decision making.
        
        Returns:
            list[BattleLogEntry]: List of battle log entries, each containing turn
                                 number and actions that occurred during that turn
        """
        try:
            # Find the battle log container
            battle_log_container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.inner.message-log"))
            )
            
            # Get the HTML content of the battle log
            battle_log_html = battle_log_container.get_attribute("innerHTML")
            log_soup = BeautifulSoup(battle_log_html, 'html.parser')
            
            # Find all turn headers (these mark the start of each turn)
            turn_header_elements = log_soup.find_all('h2', class_='battle-history')
            
            parsed_battle_log = []

            # Process Turn 0 (pre-battle actions like team preview, lead selection)
            turn_zero_actions = []
            
            # Find the first battle-history div (this contains Turn 0 actions)
            first_battle_history_element = log_soup.find('div', class_='battle-history')
            current_log_element = first_battle_history_element
            
            # Parse Turn 0 actions (everything before the first turn header)
            while current_log_element:
                # Stop when we hit the first actual turn header
                if (current_log_element.name == 'h2' and 
                    'battle-history' in current_log_element.get('class', [])):
                    break
                
                # Extract action text from battle-history divs (excluding spacers)
                if (current_log_element.name == 'div' and 
                    'battle-history' in current_log_element.get('class', []) and 
                    'spacer' not in current_log_element.get('class', [])):
                    
                    action_text = current_log_element.get_text(strip=True)
                    if action_text:
                        turn_zero_actions.append(action_text)
                
                current_log_element = current_log_element.next_sibling
            
            # Add Turn 0 to battle log if it contains actions
            if turn_zero_actions:
                turn_zero_entry = BattleLogEntry(
                    turn=0,
                    actions_in_order=turn_zero_actions
                )
                parsed_battle_log.append(turn_zero_entry)
            
            # Process each numbered turn (Turn 1, Turn 2, etc.)
            for turn_index, turn_header in enumerate(turn_header_elements):
                # Extract turn number from header text
                turn_number = int(turn_header.text.replace('Turn ', ''))
                
                # Collect all actions for this turn
                turn_actions = []
                current_log_element = turn_header.next_sibling
                
                # Parse all actions until we hit the next turn header
                while current_log_element:
                    # Stop when we encounter the next turn header
                    if (current_log_element.name == 'h2' and 
                        'battle-history' in current_log_element.get('class', [])):
                        break
                    
                    # Extract action text from battle-history divs (excluding spacers)
                    if (current_log_element.name == 'div' and 
                        'battle-history' in current_log_element.get('class', []) and 
                        'spacer' not in current_log_element.get('class', [])):
                        
                        action_text = current_log_element.get_text(strip=True)
                        if action_text:
                            turn_actions.append(action_text)
                    
                    current_log_element = current_log_element.next_sibling
                
                # Create battle log entry for this turn
                turn_entry = BattleLogEntry(
                    turn=turn_number,
                    actions_in_order=turn_actions
                )
                parsed_battle_log.append(turn_entry)
            
            return parsed_battle_log
            
        except Exception as log_parsing_error:
            self.log(f"Error parsing battle log: {log_parsing_error}")
            return []
        
    def login(self):
        """
        Authenticate with Pokemon Showdown using credentials from environment variables.
        
        This method handles the complete login process including:
        - Clicking the login button
        - Entering username
        - Entering password  
        - Handling multi-step authentication flow
        """
        try:
            # Click the main login button to start authentication
            main_login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[name='login']"))
            )
            main_login_button.click()
            
            # Wait between interactions to appear more human-like
            time.sleep(random.uniform(0.3, 1.5))
            
            # Enter username in the username field
            username_input_field = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='username']"))
            )
            
            username_input_field.clear()
            username_input_field.send_keys(os.getenv("USERNAME"))
            
            # Random delay to simulate human typing
            time.sleep(random.uniform(0.3, 1.5))
            
            # Click "Choose Name" button to proceed to password step
            choose_name_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            choose_name_button.click()
            
            # Wait for password field to appear
            time.sleep(random.uniform(0.3, 1.5))
            
            # Enter password in the password field
            password_input_field = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
            )
            
            # Additional delay before entering password
            time.sleep(random.uniform(0.3, 1.5))
            
            password_input_field.clear()
            password_input_field.send_keys(os.getenv("PASSWORD"))
            
            # Final delay before submitting
            time.sleep(random.uniform(0.3, 1.5))
            
            # Click final login button to complete authentication
            final_login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            final_login_button.click()
            
            self.log("Login process completed successfully")
            
        except Exception as login_error:
            self.log(f"Error during login process: {login_error}")
            raise login_error
    
    def paste_team(self):
        """
        Import a Pokemon team from a text file into the Showdown team builder.
        
        This method handles the complete team import process including:
        - Opening team builder
        - Creating new team
        - Importing team data from file
        - Setting battle format to Gen 9 OU
        """
        try:
            # Navigate to team builder
            teambuilder_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.button.mainmenu2[name='joinRoom'][value='teambuilder']"))
            )
            teambuilder_button.click()
            
            # Wait for team builder to load
            time.sleep(random.uniform(1, 2))

            # Create a new team
            new_team_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.button.big[name='newTop'][value='team']"))
            )
            new_team_button.click()
            
            # Wait for new team interface
            time.sleep(random.uniform(1, 2))
            
            # Click import button to open team import interface
            team_import_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.button[name='import']"))
            )
            team_import_button.click()
            
            # Wait for import interface
            time.sleep(random.uniform(1, 2))
            
            # Find the team import text area
            team_import_textarea = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.teamedit textarea.textbox"))
            )
            
            # Load team data from file
            try:
                with open("team_paste.txt", "r") as team_file:
                    team_paste_data = team_file.read()
            except FileNotFoundError:
                self.log("team_paste.txt file not found")
                return
            
            # Paste team data into the text area
            team_import_textarea.send_keys(team_paste_data)
            
            # Wait before saving
            time.sleep(random.uniform(1, 2))
            
            # Save the imported team
            save_import_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.savebutton.button[name='saveImport']"))
            )
            save_import_button.click()
            
            # Wait for save to complete
            time.sleep(random.uniform(1, 2))
            
            # Set the battle format to Gen 9 OU
            format_selector_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.select.formatselect.teambuilderformatselect[name='format']"))
            )
            format_selector_button.click()
            
            # Wait for format menu
            time.sleep(random.uniform(1, 2))
            
            # Select Gen 9 OU format
            gen9ou_format_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[name='selectFormat'][value='gen9ou']"))
            )
            gen9ou_format_button.click()
            
            # Wait for format selection
            time.sleep(random.uniform(1, 2))
            
            # Close team builder and return to main menu
            close_teambuilder_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.closebutton[name='closeRoom'][value='teambuilder']"))
            )
            close_teambuilder_button.click()
            
            self.log("Team import process completed successfully")
            
        except Exception as team_import_error:
            self.log(f"Error in team import process: {team_import_error}")
    
    def remove_banner(self):
        """
        Dismiss privacy/cookie banner if present.
        
        This method attempts to close any privacy banners that might interfere
        with the automation process. Failure is non-critical and won't stop execution.
        """
        try:
            # Click "Do Not Sell" privacy link
            privacy_dns_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.fc-dns-link[aria-label='Do Not Sell or Share My Personal Information']"))
            )
            privacy_dns_button.click()
            
            # Wait for privacy options to appear
            time.sleep(random.uniform(1, 2))
            
            # Click "Opt out" button
            opt_out_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.fc-cta-button.fc-cta-opt-out[aria-label='Opt out']"))
            )
            opt_out_button.click()
            
            self.log("Privacy banner dismissed successfully")
            
        except Exception as banner_error:
            self.log(f"Could not remove privacy banner (this is usually fine): {banner_error}")
            # This failure is non-critical, so we continue execution
    
    def initial_setup(self):
        """
        Perform complete initial setup for Pokemon Showdown automation.
        
        This method orchestrates the entire initial setup process including:
        - Navigating to Pokemon Showdown
        - Dismissing privacy banners
        - Logging into account
        - Importing Pokemon team
        - Setting battle format preferences
        """
        # Navigate to Pokemon Showdown main page
        self.driver.get("https://play.pokemonshowdown.com/")
        
        # Wait for page to load
        time.sleep(random.uniform(1, 2))
        
        # Attempt to dismiss any privacy banners
        self.remove_banner()
        
        # Wait before login
        time.sleep(random.uniform(1, 2))
        
        # Authenticate with Pokemon Showdown
        self.login()
        
        # Wait for login to complete
        time.sleep(random.uniform(1, 2))
        
        # Import Pokemon team from file
        self.paste_team()
        
        # Wait for team import to complete
        time.sleep(random.uniform(1, 2))
        
        # Set battle format to Gen 9 OU on main menu
        main_format_selector = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.select.formatselect[name='format']"))
        )
        main_format_selector.click()
        
        # Wait for format menu
        time.sleep(random.uniform(1, 2))
        
        # Select Gen 9 OU format for battles
        main_gen9ou_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[name='selectFormat'][value='gen9ou']"))
        )
        main_gen9ou_button.click()
        
        # Final wait before setup completion
        time.sleep(random.uniform(1, 2))
        
        self.log("Initial setup completed successfully")
    
    def start_battling(self):
        """
        Main execution loop for continuous Pokemon Showdown battling.
        
        This method handles the complete automation workflow:
        - Initial setup and authentication
        - Continuous battle queue and execution
        - Battle completion handling
        - Error recovery and retry logic
        """
        # Perform initial setup (login, team import, etc.)
        self.initial_setup()
        
        # Main battle loop - continues indefinitely
        while True:
            try:
                # Click battle button to join queue
                find_battle_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.button.mainmenu1.big[name='search']"))
                )
                find_battle_button.click()
                
                self.log("Searching for battle opponent...")
                
                # Wait for battle to start (indicated by battle log presence)
                battle_log_element = WebDriverWait(self.driver, 45).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.battle-log[aria-label='Battle Log']"))
                )
                
                self.log("Battle found! Starting battle execution...")
                
                try:
                    # Execute the complete battle from start to finish
                    self.start_battle()
                    
                except Exception as battle_execution_error:
                    self.log(f"Error during battle execution: {battle_execution_error}")
                    
                    # Check if battle ended despite the error
                    if self.is_battle_over():
                        self.log("Battle ended despite execution error")
                    else:
                        # Re-raise error if battle didn't end properly
                        raise battle_execution_error
                
                # Handle battle completion
                if self.is_battle_over():
                    try:
                        # Click main menu button to return to lobby
                        return_to_main_menu_button = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.button[name='closeAndMainMenu']"))
                        )
                        
                        return_to_main_menu_button.click()
                        
                        # Increment battle counter for next reasoning file
                        self.ace_trainer.current_iteration_number += 1
                        
                        self.log("Battle completed - returned to main menu")
                        
                    except Exception as cleanup_error:
                        self.log(f"Error returning to main menu: {cleanup_error}")
                
            except Exception as queue_error:
                self.log(f"Error waiting for battle to start: {queue_error}")
                raise queue_error
            
    def change_text(self, new_text_content):
        """
        Update specific page text elements (utility method for debugging).
        
        This method can change text content on the page for debugging or
        status display purposes. Currently targets official chat rooms header.
        
        Args:
            new_text_content: The text to display in the target element
        """
        try:
            # Find the official chat rooms header element
            target_header_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h2.rooms-officialchatrooms"))
            )
            
            # Change the text content using JavaScript
            self.driver.execute_script(
                "arguments[0].textContent = arguments[1];", 
                target_header_element, 
                new_text_content
            )
            
            self.log(f"Successfully changed header text to: {new_text_content}")
            
        except Exception as text_change_error:
            self.log(f"Error changing header text: {text_change_error}")
            
    def log(self, message_text: str):
        """
        Log messages to console if print mode is enabled.
        
        This method provides centralized logging control for the bot,
        allowing output to be disabled for cleaner execution.
        
        Args:
            message_text: The message to log to console
        """
        if self.print_mode:
            print(message_text)


def main():
    """
    Main entry point for the Pokemon Showdown automation bot.
    
    This function initializes the bot, starts the battling process,
    and ensures proper cleanup when the program exits.
    """
    showdown_bot = None
    try:
        # Initialize bot with verbose logging enabled
        showdown_bot = ShowdownBot(print_mode=True)
        
        # Start the continuous battling process
        showdown_bot.start_battling()
        
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        
    except Exception as main_error:
        print(f"Bot encountered an error: {main_error}")
        
    finally:
        # Ensure WebDriver is properly closed
        if showdown_bot is not None:
            showdown_bot.close()
    

if __name__ == "__main__":
    main()
        
    
        
        
