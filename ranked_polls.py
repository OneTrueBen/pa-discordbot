# Ranked Choice Poll Cog for Discord Bot
# Implements ranked choice voting with Instant-Runoff Voting (IRV) tabulation

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, Select
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
import uuid
from modrole import mod_only, owner_only, server_owner_only, get_mod_roles_for_server

class RankAssignmentSelect(Select):
    """Select menu for assigning ranks to poll options"""
    def __init__(self, options: Dict[int, str], poll_id: str, cog: 'RankedChoicePolls', current_rank: int = 1):
        self.poll_id = poll_id
        self.cog = cog
        self.options_dict = options
        self.current_rank = current_rank
        self.selected_options = set()  # Track options already selected for other ranks
        
        # Validate options
        if not options:
            raise ValueError("Options dictionary cannot be empty")

        # Check for duplicate option IDs
        if len(options) != len(set(options.keys())):
            raise ValueError("Option IDs must be unique")
        
        # Create select options from poll options
        select_options = [
            discord.SelectOption(label=option_text, value=str(option_id))
            for option_id, option_text in options.items()
        ]
        
        # Add "End Early" option to the dropdown only if this is after the first selection
        if current_rank > 1:
            select_options.append(
                discord.SelectOption(
                    label="End Early & Weigh Remaining Equally",
                    value="end_early",
                    description="Stop here and weigh remaining options equally"
                )
            )
        
        super().__init__(
            placeholder=f"Select your {self._get_rank_name(current_rank)} choice",
            min_values=1,
            max_values=1,
            options=select_options
        )
    
    def _get_rank_name(self, rank: int) -> str:
        """Convert rank number to friendly name (1st, 2nd, 3rd, etc.)"""
        if 10 <= rank % 100 <= 20:  # Special cases for 11th-13th
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(rank % 10, 'th')
        return f"{rank}{suffix}"
    
    def update_available_options(self, selected_options: set):
        """Update the available options to exclude already selected ones"""
        self.selected_options = selected_options
        
        # Create a new list of available options (excluding already selected ones)
        available_options = []
        for option in self.options:
            if str(option.value) not in {str(opt) for opt in selected_options}:
                available_options.append(option)
        
        # Filter to only include available options
        self.options = available_options
        # Reset defaults for the remaining options
        for option in self.options:
            option.default = False
        
        # Debug: Print current state
        print(f"DEBUG: update_available_options called for rank {getattr(self, 'current_rank', 'unknown')}")
        print(f"DEBUG: Selected options: {selected_options}")
        print(f"DEBUG: Available options count: {len(self.options)}")
        print(f"DEBUG: Available options: {[opt.value for opt in self.options]}")
        
    async def callback(self, interaction: discord.Interaction):
        # Check if user selected the "End Early" option
        if self.values[0] == "end_early":
            # Handle end early logic
            
            # Debug: Print the raw temp_rankings before we modify them
            print(f"DEBUG RAW TEMP RANKINGS: {self.cog.temp_rankings.get(interaction.user.id, {})}")
            print(f"DEBUG CURRENT RANK: {self.current_rank}")
            
            # Get the current user's rankings
            current_rankings = self.cog.temp_rankings.get(interaction.user.id, {}).copy()
            
            # Get all options that haven't been ranked yet
            ranked_options = set(current_rankings.values())
            all_options = set(self.options_dict.keys())
            unranked_options = all_options - ranked_options
            
            # Debug: Print what we're working with
            print(f"DEBUG BEFORE ASSIGNMENT:")
            print(f"Current rankings: {current_rankings}")
            print(f"Ranked options: {ranked_options}")
            print(f"Unranked options: {unranked_options}")
            print(f"All options: {all_options}")
            
            # Only assign remaining options if there are any unranked
            if unranked_options:
                # Assign equal weights to remaining options
                # Start from the next rank after the last assigned rank
                next_rank = max(current_rankings.keys()) + 1 if current_rankings else 1
                
                for option_id in sorted(unranked_options):
                    current_rankings[next_rank] = option_id
                    next_rank += 1
            
            # Debug: Print after assignment
            print(f"DEBUG AFTER ASSIGNMENT:")
            print(f"Current rankings: {current_rankings}")
            
            # Create final rankings list
            final_rankings = [
                current_rankings[rank]
                for rank in sorted(current_rankings.keys())
            ]
            
            # Debug: Print final rankings
            print(f"DEBUG FINAL RANKINGS: {final_rankings}")
            
            # Create a summary of the vote for confirmation
            # Split between explicitly ranked options and automatically assigned ones
            explicit_rankings = []
            auto_rankings = []
            
            # Get all options that were explicitly ranked by the user (before they chose to end early)
            explicitly_ranked_option_ids = set(self.cog.temp_rankings[interaction.user.id].values())
            all_option_ids = set(self.options_dict.keys())
            auto_option_ids = all_option_ids - explicitly_ranked_option_ids
            
            # Create explicit rankings (what user actually selected)
            for rank, option_id in self.cog.temp_rankings[interaction.user.id].items():
                explicit_rankings.append(f"{rank}. {self.options_dict[option_id]}")
            
            # Create auto rankings (remaining options to be weighed equally)
            for option_id in sorted(auto_option_ids):
                auto_rankings.append(f"{self.options_dict[option_id]}")
            
            vote_summary = "\n".join(explicit_rankings)
            if auto_rankings:
                vote_summary += f"\n\nOptions to be weighed equally:\n• " + "\n• ".join(auto_rankings)

            # Store temporary vote data before creating buttons
            self.cog.temp_votes[interaction.user.id] = {
                'poll_id': self.poll_id,
                'rankings': final_rankings,
                'timestamp': datetime.now()
            }
            
            # Create confirmation view with buttons
            view = View()
            
            confirm_button = Button(style=discord.ButtonStyle.success, label="Confirm Vote", custom_id=f"confirm_vote_{self.poll_id}_{interaction.user.id}")
            cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel", custom_id=f"cancel_vote_{self.poll_id}_{interaction.user.id}")
            
            async def confirm_callback(confirm_interaction: discord.Interaction):
                try:
                    # Submit the vote directly without modal
                    success = await self.cog._submit_vote(
                        interaction=confirm_interaction,
                        poll_id=self.poll_id,
                        user_id=confirm_interaction.user.id,
                        rankings=final_rankings
                    )
                    
                    if success:
                        # Clear temporary data
                        self.cog.temp_votes.pop(confirm_interaction.user.id, None)
                        self.cog.temp_rankings.pop(confirm_interaction.user.id, None)
                        await confirm_interaction.response.send_message("✅ Your vote has been submitted!", ephemeral=True)
                    else:
                        # Clear temporary data
                        self.cog.temp_votes.pop(confirm_interaction.user.id, None)
                        self.cog.temp_rankings.pop(confirm_interaction.user.id, None)
                        await confirm_interaction.response.send_message(
                            "❌ Failed to submit vote. The poll may be closed.",
                            ephemeral=True
                        )
                except Exception as e:
                    # Clear temporary data if something goes wrong
                    self.cog.temp_votes.pop(confirm_interaction.user.id, None)
                    self.cog.temp_rankings.pop(confirm_interaction.user.id, None)
                    await confirm_interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
            
            async def cancel_callback(cancel_interaction: discord.Interaction):
                # Clear temporary data
                self.cog.temp_votes.pop(cancel_interaction.user.id, None)
                self.cog.temp_rankings.pop(cancel_interaction.user.id, None)
                await cancel_interaction.response.send_message("❌ Vote cancelled. You can start over by clicking the Vote button again.", ephemeral=True)
            
            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            
            view.add_item(confirm_button)
            view.add_item(cancel_button)
            
            # Debug: Print the final_rankings and vote_summary to console
            print(f"DEBUG END EARLY:")
            print(f"User ID: {interaction.user.id}")
            print(f"Current rankings: {self.cog.temp_rankings.get(interaction.user.id, {})}")
            print(f"Final rankings: {final_rankings}")
            print(f"Explicit option IDs: {explicitly_ranked_option_ids}")
            print(f"Auto option IDs: {auto_option_ids}")
            print(f"Vote summary:\n{vote_summary}")
            
            await interaction.response.send_message(
                f"You chose to end ranking early. Your explicitly ranked options and the remaining equally weighed options:\n\n{vote_summary}\n\nIs this correct?",
                view=view,
                ephemeral=True
            )
            return
        
        # Handle normal option selection
        selected_value = int(self.values[0])
        
        # Store the selection for this rank
        if interaction.user.id not in self.cog.temp_rankings:
            self.cog.temp_rankings[interaction.user.id] = {}
        
        self.cog.temp_rankings[interaction.user.id][self.current_rank] = selected_value
        
        # Check if we have more ranks to assign
        if self.current_rank < len(self.options_dict):
            # Check if only one option remains for the next rank
            remaining_options = set(self.options_dict.keys()) - set(self.cog.temp_rankings[interaction.user.id].values())
            
            if len(remaining_options) == 1:
                # Automatically assign the last option without showing dropdown
                last_option = remaining_options.pop()
                self.cog.temp_rankings[interaction.user.id][self.current_rank + 1] = last_option
                
                # Check if we need to go to confirmation (all options assigned)
                if self.current_rank + 1 == len(self.options_dict):
                    # All ranks assigned, create final rankings list
                    final_rankings = [
                        self.cog.temp_rankings[interaction.user.id][rank]
                        for rank in sorted(self.cog.temp_rankings[interaction.user.id].keys())
                    ]
                    
                    # Create a summary of the vote for confirmation
                    # Split between explicitly ranked options and automatically assigned ones
                    explicit_rankings = []
                    auto_rankings = []
                    
                    # Get all options that were explicitly ranked by the user
                    explicitly_ranked_option_ids = set(self.cog.temp_rankings[interaction.user.id].values())
                    all_option_ids = set(self.options_dict.keys())
                    auto_option_ids = all_option_ids - explicitly_ranked_option_ids
                    
                    # Get the highest rank the user explicitly assigned
                    highest_explicit_rank = max(self.cog.temp_rankings[interaction.user.id].keys())
                    
                    # Create explicit rankings (what user actually selected)
                    for rank in range(1, highest_explicit_rank + 1):
                        option_id = self.cog.temp_rankings[interaction.user.id][rank]
                        explicit_rankings.append(f"{rank}. {self.options_dict[option_id]}")
                    
                    # Create auto rankings (remaining options to be weighed equally)
                    for option_id in sorted(auto_option_ids):
                        auto_rankings.append(f"{self.options_dict[option_id]}")
                    
                    vote_summary = "\n".join(explicit_rankings)
                    if auto_rankings:
                        vote_summary += f"\n\nOptions to be weighed equally:\n• " + "\n• ".join(auto_rankings)
                    
                    # Store temporary vote data before creating buttons
                    self.cog.temp_votes[interaction.user.id] = {
                        'poll_id': self.poll_id,
                        'rankings': final_rankings,
                        'timestamp': datetime.now()
                    }
                    
                    # Create confirmation view with buttons
                    view = View()
                    
                    # Create a unique custom_id that includes the user ID to avoid conflicts
                    confirm_button = Button(style=discord.ButtonStyle.success, label="Confirm Vote", custom_id=f"confirm_vote_{self.poll_id}_{interaction.user.id}")
                    cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel", custom_id=f"cancel_vote_{self.poll_id}_{interaction.user.id}")
                    
                    async def confirm_callback(confirm_interaction: discord.Interaction):
                        try:
                            # Submit the vote directly without modal
                            success = await self.cog._submit_vote(
                                interaction=confirm_interaction,
                                poll_id=self.poll_id,
                                user_id=confirm_interaction.user.id,
                                rankings=final_rankings
                            )
                            
                            if success:
                                # Clear temporary data
                                self.cog.temp_votes.pop(confirm_interaction.user.id, None)
                                self.cog.temp_rankings.pop(confirm_interaction.user.id, None)
                                await confirm_interaction.response.send_message("✅ Your vote has been submitted!", ephemeral=True)
                            else:
                                # Clear temporary data
                                self.cog.temp_votes.pop(confirm_interaction.user.id, None)
                                self.cog.temp_rankings.pop(confirm_interaction.user.id, None)
                                await confirm_interaction.response.send_message(
                                    "❌ Failed to submit vote. The poll may be closed.",
                                    ephemeral=True
                                )
                        except Exception as e:
                            # Clear temporary data if something goes wrong
                            self.cog.temp_votes.pop(confirm_interaction.user.id, None)
                            self.cog.temp_rankings.pop(confirm_interaction.user.id, None)
                            await confirm_interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
                    
                    async def cancel_callback(cancel_interaction: discord.Interaction):
                        # Clear temporary data
                        self.cog.temp_votes.pop(cancel_interaction.user.id, None)
                        self.cog.temp_rankings.pop(cancel_interaction.user.id, None)
                        await cancel_interaction.response.send_message("❌ Vote cancelled. You can start over by clicking the Vote button again.", ephemeral=True)
                    
                    confirm_button.callback = confirm_callback
                    cancel_button.callback = cancel_callback
                    
                    view.add_item(confirm_button)
                    view.add_item(cancel_button)
                    
                    await interaction.response.send_message(
                        f"Please confirm your rankings:\n\n{vote_summary}\n\nIs this correct?",
                        view=view,
                        ephemeral=True
                    )
                    return
                else:
                    # Create next rank select menu (since there are still more ranks to assign)
                    next_select = RankAssignmentSelect(
                        self.options_dict,
                        self.poll_id,
                        self.cog,
                        self.current_rank + 2  # Skip the next rank since we auto-assigned it
                    )
                    
                    # Update available options for the next menu
                    next_select.update_available_options(set(self.cog.temp_rankings[interaction.user.id].values()))
                    
                    view = View()
                    view.add_item(next_select)
                    
                    await interaction.response.send_message(
                        f"Please select your {next_select._get_rank_name(next_select.current_rank)} choice:",
                        view=view,
                        ephemeral=True
                    )
                    return
            else:
                # Create next rank select menu
                next_select = RankAssignmentSelect(
                    self.options_dict,
                    self.poll_id,
                    self.cog,
                    self.current_rank + 1
                )
                
                # Update available options for the next menu
                next_select.update_available_options(set(self.cog.temp_rankings[interaction.user.id].values()))
                
                view = View()
                view.add_item(next_select)
                
                await interaction.response.send_message(
                    f"Please select your {next_select._get_rank_name(next_select.current_rank)} choice:",
                    view=view,
                    ephemeral=True
                )
        else:
            # All ranks assigned, create final rankings list
            final_rankings = [
                self.cog.temp_rankings[interaction.user.id][rank]
                for rank in sorted(self.cog.temp_rankings[interaction.user.id].keys())
            ]
            
            # Create a summary of the vote for confirmation
            # Split between explicitly ranked options and automatically assigned ones
            explicit_rankings = []
            auto_rankings = []
            
            # Get all options that were explicitly ranked by the user
            explicitly_ranked_option_ids = set(self.cog.temp_rankings[interaction.user.id].values())
            all_option_ids = set(self.options_dict.keys())
            auto_option_ids = all_option_ids - explicitly_ranked_option_ids
            
            # Get the highest rank the user explicitly assigned
            highest_explicit_rank = max(self.cog.temp_rankings[interaction.user.id].keys())
            
            # Create explicit rankings (what user actually selected)
            for rank in range(1, highest_explicit_rank + 1):
                option_id = self.cog.temp_rankings[interaction.user.id][rank]
                explicit_rankings.append(f"{rank}. {self.options_dict[option_id]}")
            
            # Create auto rankings (remaining options to be weighed equally)
            for option_id in sorted(auto_option_ids):
                auto_rankings.append(f"{self.options_dict[option_id]}")
            
            vote_summary = "\n".join(explicit_rankings)
            if auto_rankings:
                vote_summary += f"\n\nOptions to be weighed equally:\n• " + "\n• ".join(auto_rankings)
            
            # Store temporary vote data before creating buttons
            self.cog.temp_votes[interaction.user.id] = {
                'poll_id': self.poll_id,
                'rankings': final_rankings,
                'timestamp': datetime.now()
            }
            
            # Create confirmation view with buttons
            view = View()
            
            # Create a unique custom_id that includes the user ID to avoid conflicts
            confirm_button = Button(style=discord.ButtonStyle.success, label="Confirm Vote", custom_id=f"confirm_vote_{self.poll_id}_{interaction.user.id}")
            cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel", custom_id=f"cancel_vote_{self.poll_id}_{interaction.user.id}")
            
            async def confirm_callback(confirm_interaction: discord.Interaction):
                try:
                    # Submit the vote directly without modal
                    success = await self.cog._submit_vote(
                        interaction=confirm_interaction,
                        poll_id=self.poll_id,
                        user_id=confirm_interaction.user.id,
                        rankings=final_rankings
                    )
                    
                    if success:
                        # Clear temporary data
                        self.cog.temp_votes.pop(confirm_interaction.user.id, None)
                        self.cog.temp_rankings.pop(confirm_interaction.user.id, None)
                        await confirm_interaction.response.send_message("✅ Your vote has been submitted!", ephemeral=True)
                    else:
                        # Clear temporary data
                        self.cog.temp_votes.pop(confirm_interaction.user.id, None)
                        self.cog.temp_rankings.pop(confirm_interaction.user.id, None)
                        await confirm_interaction.response.send_message(
                            "❌ Failed to submit vote. The poll may be closed.",
                            ephemeral=True
                        )
                except Exception as e:
                    # Clear temporary data if something goes wrong
                    self.cog.temp_votes.pop(confirm_interaction.user.id, None)
                    self.cog.temp_rankings.pop(confirm_interaction.user.id, None)
                    await confirm_interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
            
            async def cancel_callback(cancel_interaction: discord.Interaction):
                # Clear temporary data
                self.cog.temp_votes.pop(cancel_interaction.user.id, None)
                self.cog.temp_rankings.pop(cancel_interaction.user.id, None)
                await cancel_interaction.response.send_message("❌ Vote cancelled. You can start over by clicking the Vote button again.", ephemeral=True)
            
            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            
            view.add_item(confirm_button)
            view.add_item(cancel_button)
            
            await interaction.response.send_message(
                f"Please confirm your rankings:\n\n{vote_summary}\n\nIs this correct?",
                view=view,
                ephemeral=True
            )

class VoteConfirmationModal(Modal):
    """Modal for confirming vote submission (used by command-based voting)"""
    def __init__(self, poll_id: str, cog: 'RankedChoicePolls', rankings: List[int], options: Dict[int, str]):
        super().__init__(title="Confirm Your Vote")
        self.poll_id = poll_id
        self.cog = cog
        self.rankings = rankings
        self.options = options
        
        # Create a summary of the vote
        vote_summary = "\n".join([
            f"{i+1}. {options[option_id]}"
            for i, option_id in enumerate(rankings)
        ])
        
        self.vote_summary = discord.ui.TextInput(
            label="Your Rankings:",
            style=discord.TextStyle.paragraph,
            default=vote_summary,
            required=False
        )
        # Note: 'disabled' parameter is not available in all discord.py versions
        # We'll use the disabled property instead if needed
        self.vote_summary.disabled = True
        self.add_item(self.vote_summary)
     
    async def on_submit(self, interaction: discord.Interaction):
        # Get the temporary vote data
        temp_vote = self.cog.temp_votes.get(interaction.user.id)
        
        if not temp_vote or temp_vote['poll_id'] != self.poll_id:
            await interaction.response.send_message(
                "❌ Vote session expired. Please try voting again.",
                ephemeral=True
            )
            return
        
        # Submit the vote
        success = await self.cog._submit_vote(
            interaction=interaction,
            poll_id=self.poll_id,
            user_id=interaction.user.id,
            rankings=temp_vote['rankings']
        )
        
        if success:
            # Clear temporary vote data
            self.cog.temp_votes.pop(interaction.user.id, None)
            await interaction.response.send_message(
                "✅ Your vote has been submitted!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to submit vote. The poll may be closed.",
                ephemeral=True
            )
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(
            "❌ An error occurred while submitting your vote.",
            ephemeral=True
        )

class RankedChoicePolls(commands.Cog):
    """Ranked Choice Poll Cog for Discord Bot"""
    def __init__(self, bot):
        self.bot = bot
        self.polls: Dict[str, Dict] = {}  # In-memory poll storage
        self.temp_votes: Dict[int, Dict] = {}  # Temporary vote storage for confirmation flow
        self.temp_rankings: Dict[int, Dict[int, int]] = {}  # Temporary storage for rank assignments {user_id: {rank: option_id}}
        self.poll_tasks: Dict[str, asyncio.Task] = {}  # Tasks for poll timeouts
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Clean up any existing tasks when cog is loaded"""
        for task in self.poll_tasks.values():
            if not task.done():
                task.cancel()
        self.poll_tasks.clear()
    
    def _generate_poll_id(self) -> str:
        """Generate a unique poll ID"""
        return str(uuid.uuid4())
    
    def _create_poll_embed(self, poll: Dict, include_vote_button: bool = True) -> discord.Embed:
        """Create an embed for a poll"""
        embed = discord.Embed(
            title=f"📊 {poll['title']}",
            description=poll.get('description', '') or "No description provided",
            color=discord.Color.blue()
        )
        
        # Add poll options
        options_text = "\n".join([
            f"{option_id}. {option_text}"
            for option_id, option_text in poll['options'].items()
        ])
        embed.add_field(name="Options", value=options_text, inline=False)
        
        # Add footer with poll info
        status = "🔴 CLOSED" if poll['closed'] else "🟢 OPEN"
        embed.set_footer(text=f"Poll ID: {poll['poll_id']} | Status: {status} | Created by: <@{poll['creator_id']}>")
        
        if poll['duration']:
            end_time = poll['created_at'] + timedelta(seconds=poll['duration'])
            embed.timestamp = end_time
        
        return embed
    
    def _create_results_embed(self, poll: Dict, winners: List[Tuple[int, str]], vote_counts: Dict[int, int], rounds: List[Dict]) -> discord.Embed:
        """Create an embed for poll results"""
        embed = discord.Embed(
            title=f"🏆 Results: {poll['title']}",
            description=poll.get('description', '') or "No description provided",
            color=discord.Color.gold()
        )
        
        # Add winners
        if len(winners) == 1:
            winner_id, winner_text = winners[0]
            embed.add_field(name="Winner", value=f"{winner_id}. {winner_text}", inline=False)
        else:
            winners_text = "\n".join([f"{option_id}. {option_text}" for option_id, option_text in winners])
            embed.add_field(name="Tied Winners", value=winners_text, inline=False)
        
        # Add final vote counts
        final_counts = rounds[-1]['counts'] if rounds else vote_counts
        counts_text = "\n".join([
            f"{option_id}. {poll['options'][option_id]}: {count} votes"
            for option_id, count in final_counts.items()
        ])
        embed.add_field(name="Final Vote Counts", value=counts_text, inline=False)
        
        # Add tabulation summary if available
        if len(rounds) > 1:
            summary = "\n".join([
                f"**Round {i+1}:** Eliminated {poll['options'][round['eliminated']]} (had {round['counts'][round['eliminated']]} votes)"
                for i, round in enumerate(rounds[:-1])  # Skip last round in summary
            ])
            embed.add_field(name="Tabulation Summary", value=summary, inline=False)
        
        embed.set_footer(text=f"Poll ID: {poll['poll_id']} | Total votes: {sum(final_counts.values())}")
        
        return embed
    
    def _tabulate_results(self, poll: Dict) -> Tuple[List[Tuple[int, str]], Dict[int, int], List[Dict]]:
        """Tabulate ranked choice results using Instant-Runoff Voting (IRV)"""
        if not poll['votes']:
            # No votes - return all options as winners
            return [(option_id, option_text) for option_id, option_text in poll['options'].items()], {}, []
        
        options = set(poll['options'].keys())
        votes = poll['votes'].copy()
        rounds = []
        
        while True:
            # Count first-choice votes for each option
            vote_counts = {option_id: 0 for option_id in options}
            for user_votes in votes.values():
                if user_votes:  # If user has any rankings left
                    first_choice = next(iter(user_votes.keys()))  # Get highest remaining preference
                    vote_counts[first_choice] += 1
            
            # Check for majority
            total_votes = sum(vote_counts.values())
            majority = total_votes / 2
            
            # Record this round
            rounds.append({
                'counts': vote_counts.copy(),
                'eliminated': None
            })
            
            # Check if any option has majority
            for option_id, count in vote_counts.items():
                if count > majority:
                    # We have a winner!
                    winner = [(option_id, poll['options'][option_id])]
                    return winner, vote_counts, rounds
            
            # Check if we have a tie for first place
            max_count = max(vote_counts.values())
            leaders = [option_id for option_id, count in vote_counts.items() if count == max_count]
            
            if len(leaders) == len(options):
                # All remaining options are tied - return all as winners
                winners = [(option_id, poll['options'][option_id]) for option_id in leaders]
                return winners, vote_counts, rounds
            
            if len(leaders) > 1:
                # Tie for first place - return all tied options as winners
                winners = [(option_id, poll['options'][option_id]) for option_id in leaders]
                return winners, vote_counts, rounds
            
            # Find the option with fewest votes to eliminate
            min_count = min(vote_counts.values())
            candidates_to_eliminate = [option_id for option_id, count in vote_counts.items() if count == min_count]
            
            # If there's a tie for elimination, eliminate all tied options
            eliminated = candidates_to_eliminate[0]  # Just pick one if multiple (IRV standard)
            
            # Record elimination
            rounds[-1]['eliminated'] = eliminated
            
            # Eliminate the option
            options.remove(eliminated)
            
            # Redistribute votes - remove the eliminated option from all votes
            for user_id, user_votes in votes.items():
                if eliminated in user_votes:
                    del user_votes[eliminated]
            
            # If only one option remains, it's the winner
            if len(options) == 1:
                winner_id = next(iter(options))
                winner = [(winner_id, poll['options'][winner_id])]
                return winner, vote_counts, rounds
    
    async def _submit_vote(self, interaction: discord.Interaction, poll_id: str, user_id: int, rankings: List[int]) -> bool:
        """Submit a vote to a poll"""
        poll = self.polls.get(poll_id)
        if not poll:
            return False
        
        if poll['closed']:
            return False
        
        # Convert rankings to preference dictionary (rank -> option_id)
        vote_dict = {}
        for rank, option_id in enumerate(rankings, start=1):
            vote_dict[option_id] = rank
        
        # Store the vote
        poll['votes'][user_id] = vote_dict
        return True
    
    async def _close_poll(self, poll_id: str):
        """Close a poll and announce results"""
        poll = self.polls.get(poll_id)
        if not poll or poll['closed']:
            return
        
        poll['closed'] = True
        
        # Cancel any scheduled task
        if poll_id in self.poll_tasks:
            self.poll_tasks[poll_id].cancel()
            del self.poll_tasks[poll_id]
        
        # Tabulate results
        winners, vote_counts, rounds = self._tabulate_results(poll)
        
        # Create results embed
        embed = self._create_results_embed(poll, winners, vote_counts, rounds)
        
        # Find the original message to update
        try:
            channel = self.bot.get_channel(int(poll['channel_id']))
            if channel:
                message = await channel.fetch_message(int(poll['message_id']))
                if message:
                    await message.edit(content="⏹️ This poll has been closed", view=None, embed=embed)
                    return
        except:
            pass
        
        # If we can't find the original message, send results to the channel
        if channel:
            await channel.send(content="⏹️ Poll results:", embed=embed)
    
    async def _schedule_poll_closure(self, poll_id: str, duration: int):
        """Schedule a poll to close after the specified duration"""
        await asyncio.sleep(duration)
        await self._close_poll(poll_id)
    
    @app_commands.command(name="poll", description="Create, manage, or vote in ranked choice polls")
    @app_commands.describe(subcommand="Subcommand to execute")
    async def poll_command(self, interaction: discord.Interaction, subcommand: str):
        """Base command for poll subcommands (handled by the group)"""
        pass

    @poll_command.error
    async def poll_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandInvokeError):
            await interaction.response.send_message(
                "❌ An error occurred while executing the poll command.",
                ephemeral=True
            )
    
    @app_commands.command(name="create", description="Create a new ranked choice poll")
    @app_commands.describe(
        title="Title of the poll",
        options="Comma-separated list of options (e.g., 'Pizza, Burger, Sushi')",
        description="Description of the poll (optional)",
        duration="Duration in seconds (optional)"
    )
    async def poll_create(self, interaction: discord.Interaction, title: str, options: str, description: Optional[str] = None, duration: Optional[int] = None):
        await interaction.response.defer()
        
        # Validate inputs
        if len(title) > 100:
            await interaction.followup.send("❌ Poll title must be 100 characters or less.", ephemeral=True)
            return
            
        if description and len(description) > 500:
            await interaction.followup.send("❌ Poll description must be 500 characters or less.", ephemeral=True)
            return
        
        # Parse options
        option_list = [opt.strip() for opt in options.split(',') if opt.strip()]
        if len(option_list) < 2:
            await interaction.followup.send("❌ Poll must have at least 2 options.", ephemeral=True)
            return
        
        # Check for duplicate options
        if len(option_list) != len(set(option_list)):
            await interaction.followup.send("❌ Poll options must be unique (no duplicates).", ephemeral=True)
            return
        
        # Create poll ID and options dictionary
        poll_id = self._generate_poll_id()
        option_dict = {i+1: option_text for i, option_text in enumerate(option_list)}
        
        # Create the poll
        poll = {
            'poll_id': poll_id,
            'server_id': interaction.guild_id,
            'channel_id': str(interaction.channel_id),
            'message_id': None,  # Will be set after sending
            'creator_id': interaction.user.id,
            'title': title,
            'description': description,
            'options': option_dict,
            'votes': {},  # {user_id: {option_id: rank}}
            'created_at': datetime.now(),
            'duration': duration,
            'closed': False
        }
        
        self.polls[poll_id] = poll
        
        # Create embed
        embed = self._create_poll_embed(poll)
        
        # Create view with vote button
        view = View()
        vote_button = Button(
            label="Vote",
            style=discord.ButtonStyle.primary,
            custom_id=f"poll_vote_{poll_id}"
        )
        
        async def vote_button_callback(button_interaction: discord.Interaction):
            # Check if user has already voted
            if button_interaction.user.id in poll['votes']:
                await button_interaction.response.send_message(
                    "❌ You have already voted in this poll!",
                    ephemeral=True
                )
                return
            
            # Open rank assignment flow starting with 1st choice
            select_menu = RankAssignmentSelect(poll['options'], poll_id, self, 1)
            select_view = View()
            select_view.add_item(select_menu)
            
            await button_interaction.response.send_message(
                "Please select your 1st choice:",
                view=select_view,
                ephemeral=True
            )
        
        vote_button.callback = vote_button_callback
        view.add_item(vote_button)
        
        # Send the poll message
        message = await interaction.followup.send(
            content=f"📢 New Poll: {title}",
            embed=embed,
            view=view
        )
        
        # Update poll with message ID
        poll['message_id'] = str(message.id)
        
        # Schedule poll closure if duration is set
        if duration:
            task = asyncio.create_task(self._schedule_poll_closure(poll_id, duration))
            self.poll_tasks[poll_id] = task
        
        await interaction.followup.send(f"✅ Poll created successfully! Poll ID: `{poll_id}`", ephemeral=True)
    
    @app_commands.command(name="vote", description="Vote in a poll via command")
    @app_commands.describe(
        poll_id="ID of the poll to vote in",
        rankings="Comma-separated rankings (e.g., '1,2,3' for options 1, 2, 3)"
    )
    async def poll_vote(self, interaction: discord.Interaction, poll_id: str, rankings: str):
        await interaction.response.defer(ephemeral=True)
        
        poll = self.polls.get(poll_id)
        if not poll:
            await interaction.followup.send("❌ Poll not found. Please check the poll ID.", ephemeral=True)
            return
        
        if poll['closed']:
            await interaction.followup.send("❌ This poll is closed. Voting is no longer allowed.", ephemeral=True)
            return
        
        if interaction.user.id in poll['votes']:
            await interaction.followup.send("❌ You have already voted in this poll!", ephemeral=True)
            return
        
        # Parse rankings
        try:
            ranking_list = [int(r.strip()) for r in rankings.split(',') if r.strip()]
        except ValueError:
            await interaction.followup.send("❌ Invalid rankings format. Use comma-separated numbers (e.g., '1,2,3').", ephemeral=True)
            return
        
        # Validate rankings
        if not ranking_list:
            await interaction.followup.send("❌ No rankings provided.", ephemeral=True)
            return
        
        # Check if rankings are valid option IDs
        valid_options = set(poll['options'].keys())
        for option_id in ranking_list:
            if option_id not in valid_options:
                await interaction.followup.send(f"❌ Invalid option ID: {option_id}. Valid options are: {', '.join(map(str, valid_options))}", ephemeral=True)
                return
        
        # Check if rankings are contiguous
        if not PollOptionSelect._are_rankings_contiguous(ranking_list):
            await interaction.followup.send("❌ Invalid rankings! Please rank options without skipping numbers (e.g., 1, 2, 3 not 1, 3, 5).", ephemeral=True)
            return
        
        # Submit the vote
        success = await self._submit_vote(interaction, poll_id, interaction.user.id, ranking_list)
        
        if success:
            await interaction.followup.send("✅ Your vote has been submitted!", ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to submit vote. The poll may be closed.", ephemeral=True)
    
    @app_commands.command(name="results", description="View results of a poll")
    @app_commands.describe(poll_id="ID of the poll to view results for")
    async def poll_results(self, interaction: discord.Interaction, poll_id: str):
        await interaction.response.defer()
        
        poll = self.polls.get(poll_id)
        if not poll:
            await interaction.followup.send("❌ Poll not found. Please check the poll ID.", ephemeral=True)
            return
        
        # Tabulate results
        winners, vote_counts, rounds = self._tabulate_results(poll)
        
        # Create results embed
        embed = self._create_results_embed(poll, winners, vote_counts, rounds)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="close", description="Close a poll early")
    @app_commands.describe(poll_id="ID of the poll to close")
    async def poll_close(self, interaction: discord.Interaction, poll_id: str):
        await interaction.response.defer()

        poll = self.polls.get(poll_id)
        if not poll:
            await interaction.followup.send("❌ Poll not found. Please check the poll ID.", ephemeral=True)
            return

        if poll['closed']:
            await interaction.followup.send("❌ This poll is already closed.", ephemeral=True)
            return

        # Check permissions - only creator, mods, or bot owner can close
        if (interaction.user.id != poll['creator_id'] and
            not await mod_only()(interaction) and
            interaction.user.id != int(settings.get('owner'))):
            await interaction.followup.send("❌ You don't have permission to close this poll.", ephemeral=True)
            return
        
        # Close the poll
        await self._close_poll(poll_id)
        await interaction.followup.send(f"✅ Poll `{poll_id}` has been closed.", ephemeral=True)
    
    @poll_close.error
    async def poll_close_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have permission to close polls.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {str(error)}", ephemeral=True)
    
    @app_commands.command(name="delete", description="Delete a poll")
    @app_commands.describe(poll_id="ID of the poll to delete")
    async def poll_delete(self, interaction: discord.Interaction, poll_id: str):
        await interaction.response.defer(ephemeral=True)

        poll = self.polls.get(poll_id)
        if not poll:
            await interaction.followup.send("❌ Poll not found. Please check the poll ID.", ephemeral=True)
            return

        # Check permissions - only creator, mods, or bot owner can delete
        if (interaction.user.id != poll['creator_id'] and
            not await mod_only()(interaction) and
            interaction.user.id != int(settings.get('owner'))):
            await interaction.followup.send("❌ You don't have permission to delete this poll.", ephemeral=True)
            return
        
        # Delete the poll
        del self.polls[poll_id]
        
        # Cancel any scheduled task
        if poll_id in self.poll_tasks:
            self.poll_tasks[poll_id].cancel()
            del self.poll_tasks[poll_id]
        
        await interaction.followup.send(f"✅ Poll `{poll_id}` has been deleted.", ephemeral=True)
    
    @poll_delete.error
    async def poll_delete_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have permission to delete polls.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {str(error)}", ephemeral=True)
    
    @app_commands.command(name="list", description="List all active polls in this server")
    async def poll_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        server_polls = [
            poll for poll in self.polls.values() 
            if poll['server_id'] == interaction.guild_id and not poll['closed']
        ]
        
        if not server_polls:
            await interaction.followup.send("❌ No active polls found in this server.", ephemeral=True)
            return
        
        # Create embed
        embed = discord.Embed(
            title="📋 Active Polls",
            color=discord.Color.green()
        )
        
        for poll in server_polls:
            # Calculate time remaining if duration is set
            time_remaining = ""
            if poll['duration']:
                end_time = poll['created_at'] + timedelta(seconds=poll['duration'])
                remaining = end_time - datetime.now()
                if remaining.total_seconds() > 0:
                    hours, remainder = divmod(remaining.total_seconds(), 3600)
                    minutes, _ = divmod(remainder, 60)
                    time_remaining = f" | {int(hours)}h {int(minutes)}m remaining"
            
            embed.add_field(
                name=f"{poll['title']}",
                value=f"ID: `{poll['poll_id']}` | Created by: <@{poll['creator_id']}>{time_remaining}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle button interactions for polls"""
        if interaction.type != discord.InteractionType.component:
            return
            
        if interaction.data['custom_id'].startswith('poll_vote_'):
            poll_id = interaction.data['custom_id'][10:]  # Extract poll_id
            poll = self.polls.get(poll_id)
            
            if not poll:
                await interaction.response.send_message(
                    "❌ This poll no longer exists.",
                    ephemeral=True
                )
                return
                
            if poll['closed']:
                await interaction.response.send_message(
                    "❌ This poll is closed. Voting is no longer allowed.",
                    ephemeral=True
                )
                return
                
            if interaction.user.id in poll['votes']:
                await interaction.response.send_message(
                    "❌ You have already voted in this poll!",
                    ephemeral=True
                )
                return
            
            # Open rank assignment flow starting with 1st choice
            select_menu = RankAssignmentSelect(poll['options'], poll_id, self, 1)
            select_view = View()
            select_view.add_item(select_menu)
            
            await interaction.response.send_message(
                "Please select your 1st choice:",
                view=select_view,
                ephemeral=True
            )
        
        # Handle vote confirmation buttons
        elif interaction.data['custom_id'].startswith('confirm_vote_'):
            # Extract poll_id and user_id from custom_id (format: confirm_vote_pollid_userid)
            parts = interaction.data['custom_id'].split('_')
            if len(parts) >= 4:
                poll_id = '_'.join(parts[2:-1])  # Handle poll IDs that might contain underscores
                user_id = parts[-1]
                # This will be handled by the button callback in RankAssignmentSelect
                # We just need to make sure the interaction is processed
                await interaction.response.defer()
            return
            
        elif interaction.data['custom_id'].startswith('cancel_vote_'):
            # Extract poll_id and user_id from custom_id (format: cancel_vote_pollid_userid)
            parts = interaction.data['custom_id'].split('_')
            if len(parts) >= 4:
                poll_id = '_'.join(parts[2:-1])  # Handle poll IDs that might contain underscores
                user_id = parts[-1]
                # This will be handled by the button callback in RankAssignmentSelect
                await interaction.response.defer()
            return
            
        elif interaction.data['custom_id'].startswith('end_early_'):
            # Extract poll_id and user_id from custom_id (format: end_early_pollid_userid)
            parts = interaction.data['custom_id'].split('_')
            if len(parts) >= 4:
                poll_id = '_'.join(parts[2:-1])  # Handle poll IDs that might contain underscores
                user_id = parts[-1]
                # This will be handled by the button callback in RankAssignmentSelect
                await interaction.response.defer()
            return

async def setup(bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(RankedChoicePolls(bot))