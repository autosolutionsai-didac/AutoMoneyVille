"""
Claudeville CLI Interface
Clean, colorful terminal interface for the simulation.
"""

import os
import sys
import zlib


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Regular colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


def c(text, *styles):
    """Apply color/style to text."""
    style_str = "".join(styles)
    return f"{style_str}{text}{Colors.RESET}"


def print_header():
    """Print the Claudeville header."""
    print()
    # Box width: 65 characters inside (between ║ and ║)
    print(
        c(
            "╔" + "═" * 65 + "╗",
            Colors.CYAN,
        )
    )
    print(
        c("║", Colors.CYAN)
        + c(
            "CLAUDEVILLE SIMULATION ENGINE".center(65),
            Colors.BRIGHT_WHITE,
            Colors.BOLD,
        )
        + c("║", Colors.CYAN)
    )
    print(
        c("║", Colors.CYAN)
        + c("Generative Agents powered by Claude CLI".center(65), Colors.DIM)
        + c("║", Colors.CYAN)
    )
    print(
        c(
            "╚" + "═" * 65 + "╝",
            Colors.CYAN,
        )
    )
    print()


def print_sim_info(sim_code, fork_code, curr_time, step, personas):
    """Print current simulation information."""
    print(
        c(
            "┌─ Simulation Info ─────────────────────────────────────────────┐",
            Colors.BRIGHT_BLACK,
        )
    )
    print(c("│", Colors.BRIGHT_BLACK) + f" Name: {c(sim_code, Colors.BRIGHT_CYAN)}")
    print(c("│", Colors.BRIGHT_BLACK) + f" Fork: {c(fork_code, Colors.DIM)}")
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f" Time: {c(curr_time.strftime('%B %d, %Y %H:%M'), Colors.YELLOW)}"
    )
    print(c("│", Colors.BRIGHT_BLACK) + f" Step: {c(str(step), Colors.GREEN)}")
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f" Personas: {c(', '.join(personas), Colors.MAGENTA)}"
    )
    print(
        c(
            "└────────────────────────────────────────────────────────────────┘",
            Colors.BRIGHT_BLACK,
        )
    )
    print()


def print_help():
    """Print available commands."""
    print(
        c(
            "┌─ Commands ────────────────────────────────────────────────────┐",
            Colors.BRIGHT_BLACK,
        )
    )
    print(c("│", Colors.BRIGHT_BLACK))
    print(
        c("│", Colors.BRIGHT_BLACK)
        + c("  Simulation Control:", Colors.BRIGHT_WHITE, Colors.BOLD)
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('run <N>', Colors.GREEN)}           Run N simulation steps"
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('save', Colors.GREEN)}              Save current progress"
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('fin', Colors.GREEN)}               Save and exit"
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('quit', Colors.YELLOW)}              Exit without saving (keeps last save)"
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('discard', Colors.RED)}           Delete simulation entirely"
    )
    print(c("│", Colors.BRIGHT_BLACK))
    print(
        c("│", Colors.BRIGHT_BLACK) + c("  Status:", Colors.BRIGHT_WHITE, Colors.BOLD)
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('status', Colors.CYAN)}            Show simulation status"
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('time', Colors.CYAN)}              Show current sim time"
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('personas', Colors.CYAN)}          List all personas"
    )
    print(c("│", Colors.BRIGHT_BLACK))
    print(
        c("│", Colors.BRIGHT_BLACK)
        + c("  Persona Info:", Colors.BRIGHT_WHITE, Colors.BOLD)
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('schedule <name>', Colors.MAGENTA)}    Show persona's schedule"
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('location <name>', Colors.MAGENTA)}    Show persona's location"
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('memory <name>', Colors.MAGENTA)}      Show persona's memories"
    )
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('chat <name>', Colors.MAGENTA)}        Start chat with persona"
    )
    print(c("│", Colors.BRIGHT_BLACK))
    print(
        c("│", Colors.BRIGHT_BLACK)
        + f"    {c('help', Colors.BRIGHT_WHITE)}              Show this help"
    )
    print(c("│", Colors.BRIGHT_BLACK))
    print(
        c(
            "└────────────────────────────────────────────────────────────────┘",
            Colors.BRIGHT_BLACK,
        )
    )
    print()


def print_step_start(step, curr_time):
    """Print step start indicator."""
    time_str = curr_time.strftime("%H:%M")
    print(
        c(f"▶ Step {step}", Colors.GREEN, Colors.BOLD) + c(f" @ {time_str}", Colors.DIM)
    )


def print_persona_action(persona_name, action, emoji=""):
    """Print a persona's current action."""
    name_colors = {
        0: Colors.BRIGHT_CYAN,
        1: Colors.BRIGHT_MAGENTA,
        2: Colors.BRIGHT_YELLOW,
        3: Colors.BRIGHT_GREEN,
        4: Colors.BRIGHT_BLUE,
    }
    # Stable hash (Python's built-in hash() is salted per process, so colors
    # would change between runs); crc32 is deterministic across runs (ARCH-14).
    color = name_colors[zlib.crc32(persona_name.encode()) % len(name_colors)]

    emoji_str = f" {emoji}" if emoji else ""
    print(
        f"  {c('●', color)} {c(persona_name, color, Colors.BOLD)}: {action}{emoji_str}"
    )


def print_step_complete(step, duration_ms=None):
    """Print step completion."""
    duration_str = f" ({duration_ms}ms)" if duration_ms else ""
    print(c(f"  ✓ Step {step} complete{duration_str}", Colors.DIM))
    print()


def print_persona_movement(persona_name, from_tile, to_tile):
    """Print persona movement."""
    print(c(f"    → moved from {from_tile} to {to_tile}", Colors.DIM))


def print_conversation_start(persona1, persona2):
    """Print conversation start."""
    print(c(f"  💬 {persona1} started talking with {persona2}", Colors.BRIGHT_YELLOW))


def print_conversation_line(speaker, text):
    """Print a line of conversation."""
    print(f"     {c(speaker + ':', Colors.BRIGHT_WHITE)} {text}")


def print_error(message):
    """Print an error message."""
    print(c(f"✗ Error: {message}", Colors.BRIGHT_RED))


def print_success(message):
    """Print a success message."""
    print(c(f"✓ {message}", Colors.BRIGHT_GREEN))


def print_warning(message):
    """Print a warning message."""
    print(c(f"⚠ {message}", Colors.BRIGHT_YELLOW))


def print_info(message):
    """Print an info message."""
    print(c(f"ℹ {message}", Colors.BRIGHT_CYAN))


def print_schedule(persona_name, schedule_items):
    """Print a persona's schedule in a nice format."""
    print(
        c(
            f"┌─ {persona_name}'s Schedule ─────────────────────────────────────┐",
            Colors.MAGENTA,
        )
    )
    for time_str, activity in schedule_items:
        print(c("│", Colors.MAGENTA) + f" {c(time_str, Colors.YELLOW)} {activity}")
    print(
        c(
            "└────────────────────────────────────────────────────────────────┘",
            Colors.MAGENTA,
        )
    )
    print()


def print_memory_summary(persona_name, events_count, thoughts_count, chats_count):
    """Print a summary of persona's memories."""
    print(
        c(
            f"┌─ {persona_name}'s Memory ───────────────────────────────────────┐",
            Colors.BLUE,
        )
    )
    print(c("│", Colors.BLUE) + f" Events:   {c(str(events_count), Colors.GREEN)}")
    print(c("│", Colors.BLUE) + f" Thoughts: {c(str(thoughts_count), Colors.CYAN)}")
    print(c("│", Colors.BLUE) + f" Chats:    {c(str(chats_count), Colors.YELLOW)}")
    print(
        c(
            "└────────────────────────────────────────────────────────────────┘",
            Colors.BLUE,
        )
    )
    print()


def get_prompt():
    """Get user input with a styled prompt."""
    try:
        return input(
            c("claudeville", Colors.CYAN, Colors.BOLD) + c(" ▸ ", Colors.BRIGHT_BLACK)
        ).strip()
    except EOFError:
        return "quit"
    except KeyboardInterrupt:
        print()
        return ""


def print_startup_menu(default_fork, last_sim):
    """Print the startup menu."""
    print_header()

    print(c("  Base template: ", Colors.DIM) + c(default_fork, Colors.BRIGHT_CYAN))
    if last_sim:
        print(c("  Last session:  ", Colors.DIM) + c(last_sim, Colors.BRIGHT_GREEN))
    print()

    print(c("  What would you like to do?", Colors.BRIGHT_WHITE))
    print()
    print(f"    {c('[Enter]', Colors.GREEN, Colors.BOLD)}  Start new simulation")
    if last_sim:
        print(
            f"    {c('[c]', Colors.YELLOW, Colors.BOLD)}      Continue last simulation"
        )
    print(f"    {c('[custom]', Colors.MAGENTA, Colors.BOLD)} Custom fork/name")
    print()


def print_simulation_started(sim_name):
    """Print simulation started message."""
    print()
    print(c("═" * 66, Colors.GREEN))
    print(c(f"  Simulation started: {sim_name}", Colors.BRIGHT_GREEN, Colors.BOLD))
    print(c("═" * 66, Colors.GREEN))
    print()
    print(
        c("  Frontend: ", Colors.DIM)
        + c("http://localhost:8000/simulator_home", Colors.BRIGHT_CYAN, Colors.BOLD)
    )
    print()
    print(
        c(
            "  Type 'help' for available commands, or 'run <N>' to simulate steps.",
            Colors.DIM,
        )
    )
    print()


def print_run_progress(current, total, persona_statuses):
    """Print progress during a run."""
    pct = int((current / total) * 100)
    bar_width = 40
    filled = int(bar_width * current / total)
    bar = "█" * filled + "░" * (bar_width - filled)

    # Clear line and print progress
    sys.stdout.write(
        f"\r  {c('[' + bar + ']', Colors.GREEN)} {c(f'{pct}%', Colors.BRIGHT_WHITE)} ({current}/{total})"
    )
    sys.stdout.flush()


def print_run_complete(steps, total_time_sec):
    """Print run completion summary."""
    print()  # New line after progress bar
    print()
    print(
        c(
            f"  ✓ Completed {steps} steps in {total_time_sec:.1f}s",
            Colors.BRIGHT_GREEN,
            Colors.BOLD,
        )
    )
    print()


def clear_screen():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")
