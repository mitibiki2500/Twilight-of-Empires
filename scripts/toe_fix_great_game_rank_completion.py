from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "common/journal_entries/00_player_objectives_great_game.txt"
text = p.read_text(encoding="utf-8-sig", errors="strict")
had_bom = p.read_bytes().startswith(b"\xef\xbb\xbf")

old_complete = '''            custom_description = {
                text = toe_gg_tegar_score_victory_tt
                global_var:toe_great_game_score <= 70
            }
            AND = {
                c:XAI ?= { country_rank < rank_value:great_power }
                c:GOT ?= { country_rank < rank_value:great_power }
                c:GSU ?= { country_rank >= rank_value:great_power }
                c:PAI ?= { country_rank >= rank_value:great_power }
            }
            AND = {
                c:GSU ?= { country_rank < rank_value:great_power }
                c:PAI ?= { country_rank < rank_value:great_power }
                c:XAI ?= { country_rank >= rank_value:great_power }
                c:GOT ?= { country_rank >= rank_value:great_power }
            }
'''
new_complete = '''            custom_description = {
                text = toe_gg_tegar_score_victory_tt
                global_var:toe_great_game_score <= 70
            }
'''
if text.count(old_complete) != 1:
    raise RuntimeError(f"rank completion block expected once, got {text.count(old_complete)}")
text = text.replace(old_complete, new_complete, 1)

old_winner = '''                limit = {
                    OR = {
                        global_var:toe_great_game_score >= 130
                        AND = {
                            c:XAI ?= { country_rank < rank_value:great_power }
                            c:GOT ?= { country_rank < rank_value:great_power }
                            c:GSU ?= { country_rank >= rank_value:great_power }
                            c:PAI ?= { country_rank >= rank_value:great_power }
                        }
                    }
                }
'''
new_winner = '''                limit = {
                    global_var:toe_great_game_score >= 130
                }
'''
if text.count(old_winner) != 1:
    raise RuntimeError(f"rank winner block expected once, got {text.count(old_winner)}")
text = text.replace(old_winner, new_winner, 1)

# Great Game victory is intentionally score-only; rank changes must not resolve it.
if "country_rank" in text:
    raise RuntimeError("country_rank still participates in Great Game control JE")
if "global_var:toe_great_game_score >= 130" not in text or "global_var:toe_great_game_score <= 70" not in text:
    raise RuntimeError("score victory thresholds missing")

p.write_text(text, encoding="utf-8-sig" if had_bom else "utf-8")
print("TOE_GREAT_GAME_SCORE_ONLY_COMPLETION_OK")
