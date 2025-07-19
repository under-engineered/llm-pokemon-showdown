"""
Pokemon Showdown AI Battle Assistant - Ace Trainer Module

This module provides an AI-powered battle decision maker for Pokemon Showdown.
It uses Claude (Anthropic's LLM) to analyze battle situations and generate
optimal moves based on team composition, battle state, and strategic considerations.

Author: LLM Pokemon Showdown Project
Dependencies: langchain_anthropic, pydantic, python-dotenv
Usage: Used by the main ShowdownBot to make intelligent battle decisions
"""

import os
from typing import Literal

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field


def check_iteration_number() -> int:
    """
    Check how many reasoning files exist in the reasoning directory.
    
    This function counts the number of files in the 'reasoning' directory
    to determine the current iteration/battle number for file naming purposes.
    
    Returns:
        int: The number of existing reasoning files, or 0 if directory doesn't exist
    """
    try:
        reasoning_directory = "reasoning"
        
        # Create reasoning directory if it doesn't exist
        if not os.path.exists(reasoning_directory):
            os.makedirs(reasoning_directory)
            return 0
            
        # Count files in the reasoning directory
        reasoning_files = [
            filename for filename in os.listdir(reasoning_directory) 
            if os.path.isfile(os.path.join(reasoning_directory, filename))
        ]
        
        return len(reasoning_files)
        
    except Exception as error:
        print(f"Error checking reasoning files: {error}")
        return 0


class BattleMove(BaseModel):
    """
    Pydantic model representing a battle decision made by the AI trainer.
    
    This model ensures that the AI's decisions are properly structured
    and validated before being executed in the battle.
    """
    action: Literal[
        "Move 1", "Move 2", "Move 3", "Move 4", 
        "Switch 1", "Switch 2", "Switch 3", "Switch 4", "Switch 5", "Switch 6"
    ] = Field(
        description="The move to use (Move 1-4) or the Pokemon to switch to (Switch 1-6)."
    )
    
    terastallize: bool = Field(
        description="Whether to Terastallize the Pokemon during this turn. Can only be used once per battle."
    )
    
    reason: str = Field(
        description="Brief explanation (less than 50 characters) for this decision."
    )


class AceTrainer:
    """
    AI-powered Pokemon battle strategist using Claude LLM.
    
    This class handles the interaction with Claude to generate battle decisions
    based on the current battle state, team information, and strategic analysis.
    """
    
    def __init__(self, battle_move_structure: BaseModel):
        """
        Initialize the Ace Trainer with Claude LLM integration.
        
        Args:
            battle_move_structure: Pydantic model defining the structure of battle moves
        """
        # Load environment variables (API keys, etc.)
        load_dotenv()
        
        # Initialize Claude LLM with structured output
        claude_llm = ChatAnthropic(
            model="claude-sonnet-4-20250514", 
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        
        # Configure LLM to return structured BattleMove objects
        self.llm = claude_llm.with_structured_output(BattleMove, method="json_schema")
        
        # Track current battle iteration for file naming
        self.current_iteration_number = check_iteration_number()
    
    def make_trainer_prompt(self, battle_instruction: str) -> tuple[str, str]:
        """
        Create system and user prompts for the AI trainer.
        
        This method constructs the prompts that will be sent to Claude,
        including team information and battle context.
        
        Args:
            battle_instruction: Current battle situation and available options
            
        Returns:
            tuple: (system_prompt, user_prompt) for the LLM
        """
        try:
            # Load team composition with explanations
            with open("team_with_explanations.txt", "r") as team_file:
                team_composition_with_explanations = team_file.read()
                
        except FileNotFoundError:
            # Fallback: ask user to provide team information manually
            team_composition_with_explanations = input(
                "Error: team_with_explanations.txt not found. Please paste it here: \n"
            )
            
        # Construct the system prompt with trainer personality and context
        system_prompt = f"""You are an ACE pokemon trainer participating in a Pokemon Showdown battle. The format you are competing in is Gen 9 OU. You are given a scenario and you need to generate the next move.
Your goal is to win the battle. Do NOT go easy on the opponent.

Below is the team you are using with explanations:
{team_composition_with_explanations}"""

        user_prompt = battle_instruction
        
        return system_prompt, user_prompt
    
    def generate_battle_moves(self, battle_instruction: str):
        """
        Generate the next battle move using AI analysis.
        
        This is the main method that takes the current battle state and returns
        an optimal move decision with reasoning.
        
        Args:
            battle_instruction: Detailed description of current battle situation
            
        Returns:
            tuple: (BattleMove object, reasoning_string) containing the decision and explanation
        """
        # Create prompts for the LLM
        system_prompt, user_prompt = self.make_trainer_prompt(battle_instruction)
        
        # Prepare messages for Claude
        llm_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            # Get battle decision from Claude
            ai_response = self.llm.invoke(llm_messages)
            
        except Exception as llm_error:
            print(f"Error generating battle moves: {llm_error}")
            raise llm_error
        
        # Display the decision with colorful terminal output
        self._display_battle_decision(ai_response)
        
        # Format reasoning for file storage
        reasoning_text = (
            f"Action: {ai_response.action}\n"
            f"Terastallize: {ai_response.terastallize}\n"
            f"Reason: {ai_response.reason}"
        )
        
        # Save reasoning to file for analysis
        self._save_reasoning_to_file(reasoning_text)
        
        return ai_response, reasoning_text
    
    def _display_battle_decision(self, battle_response: BattleMove) -> None:
        """
        Display the AI's battle decision with colorful terminal formatting.
        
        Args:
            battle_response: The BattleMove decision from the AI
        """
        # Terminal color codes for enhanced display
        BOLD = '\033[1m'
        GREEN = '\033[92m'
        BLUE = '\033[94m'  
        YELLOW = '\033[93m'
        RED = '\033[91m'
        PURPLE = '\033[95m'
        CYAN = '\033[96m'
        END_COLOR = '\033[0m'
        
        # Create visual separator
        print("\n" + "="*50)
        print("⚡ 🎯 BATTLE DECISION 🎯 ⚡")
        print("="*50)
        
        # Display action with appropriate emoji
        action_emoji = "⚔️" if "Move" in battle_response.action else "🔄"
        print(f"{BOLD}{GREEN}🎮 ACTION:{END_COLOR} {action_emoji} {YELLOW}{battle_response.action}{END_COLOR}")
        
        # Display Terastallize decision with visual indicators
        terastallize_status = "✨ YES ✨" if battle_response.terastallize else "❌ NO"
        terastallize_color = PURPLE if battle_response.terastallize else RED
        print(f"{BOLD}{BLUE}💎 TERASTALLIZE:{END_COLOR} {terastallize_color}{terastallize_status}{END_COLOR}")
        
        # Display reasoning
        print(f"{BOLD}{CYAN}🧠 REASONING:{END_COLOR} {battle_response.reason}")
        
        print("="*50 + "\n")
    
    def _save_reasoning_to_file(self, reasoning_content: str) -> None:
        """
        Save the AI's reasoning to a numbered file for later analysis.
        
        Args:
            reasoning_content: The formatted reasoning string to save
        """
        try:
            # Ensure reasoning directory exists
            os.makedirs("reasoning", exist_ok=True)
            
            # Save reasoning to numbered file
            reasoning_filename = f"reasoning/{self.current_iteration_number}.txt"
            with open(reasoning_filename, "a") as reasoning_file:
                reasoning_file.write(reasoning_content)
                
        except Exception as file_error:
            print(f"Error saving reasoning to file: {file_error}")
    