from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {n}")
    return text.replace(old, new, 1)


def write_preserving_bom(path: Path, text: str) -> None:
    had_bom = path.read_bytes().startswith(b"\xef\xbb\xbf")
    path.write_text(text, encoding="utf-8-sig" if had_bom else "utf-8")


def fix_geography() -> None:
    p = ROOT / "common/scripted_triggers/00_geography_triggers.txt"
    text = p.read_text(encoding="utf-8-sig", errors="strict")
    old = '''\t\tany_scope_state = {
\t\t\tOR = {
\t\t\t\tstate_region = s:STATE_CALIFORNIA
\t\t\t\tstate_region = s:STATE_NEVADA
\t\t\t\tstate_region = s:STATE_ARIZONA
\t\t\t\tstate_region = s:STATE_UTAH
\t\t\t\tstate_region = s:STATE_LOWLANDS
\t\t\t\tstate_region = s:STATE_HIGHLANDS
\t\t\t\tstate_region = s:STATE_ULSTER
\t\t\t\tstate_region = s:STATE_LEINSTER
\t\t\t\tstate_region = s:STATE_CONNAUGHT
\t\t\t\tstate_region = s:STATE_MUNSTER
\t\t\t}
\t\t}

'''
    new = '''\t\t# ToE 1.13 compatibility: removed vanilla-only state aliases.
\t\t# Custom-map equivalents are not defined here; do not guess-map them.
'''
    text = replace_once(text, old, new, "drought vanilla-state block")
    write_preserving_bom(p, text)


BASELINE_AND_SUBJOURNALS = r'''
        # ToE: starting-map conditions are a baseline, not points earned during play.
        # Mark already-satisfied objectives as settled without changing the score.
        if = {
            limit = {
                c:PAI ?= {
                    any_scope_state = {
                        OR = {
                            state_region = s:STATE_NSM_041
                            state_region = s:STATE_NSM_062
                            state_region = s:STATE_NSM_079
                            state_region = s:STATE_NSM_126
                            state_region = s:STATE_NSM_129
                            state_region = s:STATE_NSM_344
                            state_region = s:STATE_NSM_374
                            state_region = s:STATE_NSM_389
                            state_region = s:STATE_NSM_407
                            state_region = s:STATE_NSM_433
                            state_region = s:STATE_NSM_452
                            state_region = s:STATE_NSM_526
                        }
                        count >= 6
                    }
                }
            }
            set_global_variable = toe_gg_steppe_done
            set_global_variable = { name = toe_gg_steppe_side value = 1 }
        }
        else_if = {
            limit = {
                c:GOT ?= {
                    any_scope_state = {
                        OR = {
                            state_region = s:STATE_NSM_041
                            state_region = s:STATE_NSM_062
                            state_region = s:STATE_NSM_079
                            state_region = s:STATE_NSM_126
                            state_region = s:STATE_NSM_129
                            state_region = s:STATE_NSM_344
                            state_region = s:STATE_NSM_374
                            state_region = s:STATE_NSM_389
                            state_region = s:STATE_NSM_407
                            state_region = s:STATE_NSM_433
                            state_region = s:STATE_NSM_452
                            state_region = s:STATE_NSM_526
                        }
                        count >= 6
                    }
                }
            }
            set_global_variable = toe_gg_steppe_done
            set_global_variable = { name = toe_gg_steppe_side value = -1 }
        }

        if = {
            limit = {
                c:SOS ?= {
                    OR = {
                        is_subject_of = c:PAI
                        power_bloc ?= { c:PAI ?= this.power_bloc_leader }
                    }
                    relations:c:PAI >= 50
                    liberty_desire <= 25
                }
            }
            set_global_variable = toe_gg_sosilia_done
        }

        if = {
            limit = {
                s:STATE_NSM_258 = {
                    owner = {
                        OR = {
                            this = c:PAI
                            is_subject_of = c:PAI
                            power_bloc ?= { c:PAI ?= this.power_bloc_leader }
                        }
                    }
                }
                s:STATE_NSM_430 = {
                    owner = {
                        OR = {
                            this = c:PAI
                            is_subject_of = c:PAI
                            power_bloc ?= { c:PAI ?= this.power_bloc_leader }
                        }
                    }
                }
            }
            set_global_variable = toe_gg_plains_done
        }

        if = {
            limit = {
                s:STATE_NSM_525 = {
                    owner = {
                        OR = {
                            this = c:PAI
                            is_subject_of = c:PAI
                            power_bloc ?= { c:PAI ?= this.power_bloc_leader }
                            this = c:GSU
                            is_subject_of = c:GSU
                            power_bloc ?= { c:GSU ?= this.power_bloc_leader }
                        }
                    }
                }
            }
            set_global_variable = toe_gg_route_done
            set_global_variable = { name = toe_gg_route_side value = 1 }
        }
        else_if = {
            limit = {
                s:STATE_NSM_525 = {
                    owner = {
                        OR = {
                            this = c:XAI
                            is_subject_of = c:XAI
                            power_bloc ?= { c:XAI ?= this.power_bloc_leader }
                            this = c:GOT
                            is_subject_of = c:GOT
                            power_bloc ?= { c:GOT ?= this.power_bloc_leader }
                        }
                    }
                }
            }
            set_global_variable = toe_gg_route_done
            set_global_variable = { name = toe_gg_route_side value = -1 }
        }

        if = {
            limit = {
                any_state = {
                    count >= 5
                    OR = {
                        region = sr:region_nsm_north_ria
                        region = sr:region_nsm_west_ria
                        region = sr:region_nsm_east_ria
                        region = sr:region_nsm_south_ria
                    }
                    NOT = { state_region = s:STATE_NSM_169 }
                    NOT = { state_region = s:STATE_NSM_204 }
                    NOT = { state_region = s:STATE_NSM_227 }
                    NOT = { state_region = s:STATE_NSM_292 }
                    NOT = { state_region = s:STATE_NSM_299 }
                    NOT = { state_region = s:STATE_NSM_418 }
                    NOT = { state_region = s:STATE_NSM_456 }
                    NOT = { state_region = s:STATE_NSM_484 }
                    NOT = { state_region = s:STATE_NSM_499 }
                    NOT = { state_region = s:STATE_NSM_500 }
                    NOT = { state_region = s:STATE_NSM_509 }
                    owner = {
                        OR = {
                            this = c:XAI
                            is_subject_of = c:XAI
                            power_bloc ?= { c:XAI ?= this.power_bloc_leader }
                        }
                    }
                }
            }
            set_global_variable = toe_gg_tegar_ria_done
        }

        if = {
            limit = {
                NOT = {
                    any_state = {
                        OR = {
                            region = sr:region_nsm_north_ria
                            region = sr:region_nsm_west_ria
                            region = sr:region_nsm_east_ria
                            region = sr:region_nsm_south_ria
                        }
                        owner = {
                            OR = {
                                this = c:XAI
                                is_subject_of = c:XAI
                                power_bloc ?= { c:XAI ?= this.power_bloc_leader }
                            }
                        }
                    }
                }
            }
            set_global_variable = toe_gg_ilvone_expel_done
        }

        if = {
            limit = {
                c:XCI ?= {
                    OR = {
                        is_subject_of = c:GSU
                        power_bloc ?= { c:GSU ?= this.power_bloc_leader }
                    }
                }
            }
            set_global_variable = toe_gg_tortal_done
            set_global_variable = { name = toe_gg_tortal_side value = 1 }
        }
        else_if = {
            limit = {
                c:XCI ?= {
                    OR = {
                        is_subject_of = c:XAI
                        power_bloc ?= { c:XAI ?= this.power_bloc_leader }
                    }
                }
            }
            set_global_variable = toe_gg_tortal_done
            set_global_variable = { name = toe_gg_tortal_side value = -1 }
        }

        if = {
            limit = {
                any_state = {
                    count >= 5
                    region = sr:region_nsm_south_lefria
                    owner = {
                        OR = {
                            this = c:GSU
                            is_subject_of = c:GSU
                            power_bloc ?= { c:GSU ?= this.power_bloc_leader }
                        }
                    }
                }
            }
            set_global_variable = toe_gg_south_lefria_done
            set_global_variable = { name = toe_gg_south_lefria_side value = 1 }
        }
        else_if = {
            limit = {
                any_state = {
                    count >= 5
                    region = sr:region_nsm_south_lefria
                    owner = {
                        OR = {
                            this = c:XAI
                            is_subject_of = c:XAI
                            power_bloc ?= { c:XAI ?= this.power_bloc_leader }
                        }
                    }
                }
            }
            set_global_variable = toe_gg_south_lefria_done
            set_global_variable = { name = toe_gg_south_lefria_side value = -1 }
        }

        # Add the visible objective JEs to each participant. Previously they were only defined.
        if = {
            limit = { c:PAI = THIS }
            if = { limit = { NOT = { has_global_variable = toe_gg_steppe_done } } add_journal_entry = { type = je_toe_gg_steppe } }
            if = { limit = { NOT = { has_global_variable = toe_gg_sosilia_done } } add_journal_entry = { type = je_toe_gg_sosilia } }
            if = { limit = { NOT = { has_global_variable = toe_gg_plains_done } } add_journal_entry = { type = je_toe_gg_plains } }
            if = { limit = { NOT = { has_global_variable = toe_gg_route_done } } add_journal_entry = { type = je_toe_gg_route } }
        }
        else_if = {
            limit = { c:GOT = THIS }
            if = { limit = { NOT = { has_global_variable = toe_gg_steppe_done } } add_journal_entry = { type = je_toe_gg_steppe } }
            if = { limit = { NOT = { has_global_variable = toe_gg_route_done } } add_journal_entry = { type = je_toe_gg_route } }
        }
        else_if = {
            limit = { c:XAI = THIS }
            if = { limit = { NOT = { has_global_variable = toe_gg_route_done } } add_journal_entry = { type = je_toe_gg_route } }
            if = { limit = { NOT = { has_global_variable = toe_gg_tegar_ria_done } } add_journal_entry = { type = je_toe_gg_tegar_ria } }
            if = { limit = { NOT = { has_global_variable = toe_gg_tortal_done } } add_journal_entry = { type = je_toe_gg_tortal } }
            if = { limit = { NOT = { has_global_variable = toe_gg_south_lefria_done } } add_journal_entry = { type = je_toe_gg_south_lefria } }
        }
        else_if = {
            limit = { c:GSU = THIS }
            if = { limit = { NOT = { has_global_variable = toe_gg_route_done } } add_journal_entry = { type = je_toe_gg_route } }
            if = { limit = { NOT = { has_global_variable = toe_gg_ilvone_expel_done } } add_journal_entry = { type = je_toe_gg_expel_tegar_ria } }
            if = { limit = { NOT = { has_global_variable = toe_gg_tortal_done } } add_journal_entry = { type = je_toe_gg_tortal } }
            if = { limit = { NOT = { has_global_variable = toe_gg_south_lefria_done } } add_journal_entry = { type = je_toe_gg_south_lefria } }
        }
'''


def fix_great_game_parent() -> None:
    p = ROOT / "common/journal_entries/00_player_objectives_great_game.txt"
    text = p.read_text(encoding="utf-8-sig", errors="strict")
    anchor = '''            set_global_variable = { name = great_game_rus_progress value = 100 }
        }

    }
'''
    replacement = '''            set_global_variable = { name = great_game_rus_progress value = 100 }
''' + BASELINE_AND_SUBJOURNALS + '''        }
        else = {
            # Initialization has already happened globally, but each participant still needs its own visible sub-JEs.
            if = {
                limit = { c:PAI = THIS }
                if = { limit = { NOT = { has_global_variable = toe_gg_steppe_done } } add_journal_entry = { type = je_toe_gg_steppe } }
                if = { limit = { NOT = { has_global_variable = toe_gg_sosilia_done } } add_journal_entry = { type = je_toe_gg_sosilia } }
                if = { limit = { NOT = { has_global_variable = toe_gg_plains_done } } add_journal_entry = { type = je_toe_gg_plains } }
                if = { limit = { NOT = { has_global_variable = toe_gg_route_done } } add_journal_entry = { type = je_toe_gg_route } }
            }
            else_if = {
                limit = { c:GOT = THIS }
                if = { limit = { NOT = { has_global_variable = toe_gg_steppe_done } } add_journal_entry = { type = je_toe_gg_steppe } }
                if = { limit = { NOT = { has_global_variable = toe_gg_route_done } } add_journal_entry = { type = je_toe_gg_route } }
            }
            else_if = {
                limit = { c:XAI = THIS }
                if = { limit = { NOT = { has_global_variable = toe_gg_route_done } } add_journal_entry = { type = je_toe_gg_route } }
                if = { limit = { NOT = { has_global_variable = toe_gg_tegar_ria_done } } add_journal_entry = { type = je_toe_gg_tegar_ria } }
                if = { limit = { NOT = { has_global_variable = toe_gg_tortal_done } } add_journal_entry = { type = je_toe_gg_tortal } }
                if = { limit = { NOT = { has_global_variable = toe_gg_south_lefria_done } } add_journal_entry = { type = je_toe_gg_south_lefria } }
            }
            else_if = {
                limit = { c:GSU = THIS }
                if = { limit = { NOT = { has_global_variable = toe_gg_route_done } } add_journal_entry = { type = je_toe_gg_route } }
                if = { limit = { NOT = { has_global_variable = toe_gg_ilvone_expel_done } } add_journal_entry = { type = je_toe_gg_expel_tegar_ria } }
                if = { limit = { NOT = { has_global_variable = toe_gg_tortal_done } } add_journal_entry = { type = je_toe_gg_tortal } }
                if = { limit = { NOT = { has_global_variable = toe_gg_south_lefria_done } } add_journal_entry = { type = je_toe_gg_south_lefria } }
            }
        }

    }
'''
    text = replace_once(text, anchor, replacement, "Great Game immediate")

    text = replace_once(
        text,
        '''            global_var:toe_great_game_score >= 130
            global_var:toe_great_game_score <= 70
''',
        '''            custom_description = {
                text = toe_gg_ilvone_score_victory_tt
                global_var:toe_great_game_score >= 130
            }
            custom_description = {
                text = toe_gg_tegar_score_victory_tt
                global_var:toe_great_game_score <= 70
            }
''',
        "Great Game completion score conditions",
    )
    write_preserving_bom(p, text)


SUBJOURNAL_SCORE_LOCS = {
    "je_toe_gg_steppe": "toe_gg_steppe_complete_tt",
    "je_toe_gg_sosilia": "toe_gg_sosilia_complete_tt",
    "je_toe_gg_plains": "toe_gg_plains_complete_tt",
    "je_toe_gg_route": "toe_gg_route_complete_tt",
    "je_toe_gg_tegar_ria": "toe_gg_tegar_ria_complete_tt",
    "je_toe_gg_expel_tegar_ria": "toe_gg_expel_complete_tt",
    "je_toe_gg_tortal": "toe_gg_tortal_complete_tt",
    "je_toe_gg_south_lefria": "toe_gg_south_lefria_complete_tt",
}
SUBJOURNAL_FLAGS = {
    "je_toe_gg_steppe": "toe_gg_steppe_done",
    "je_toe_gg_sosilia": "toe_gg_sosilia_done",
    "je_toe_gg_plains": "toe_gg_plains_done",
    "je_toe_gg_route": "toe_gg_route_done",
    "je_toe_gg_tegar_ria": "toe_gg_tegar_ria_done",
    "je_toe_gg_expel_tegar_ria": "toe_gg_ilvone_expel_done",
    "je_toe_gg_tortal": "toe_gg_tortal_done",
    "je_toe_gg_south_lefria": "toe_gg_south_lefria_done",
}


def fix_subjournal_conditions() -> None:
    p = ROOT / "common/journal_entries/99_toe_great_game_subjournals.txt"
    text = p.read_text(encoding="utf-8-sig", errors="strict")
    for je, loc in SUBJOURNAL_SCORE_LOCS.items():
        flag = SUBJOURNAL_FLAGS[je]
        old = f"    complete = {{ has_global_variable = {flag} }}"
        new = f'''    complete = {{
        custom_description = {{
            text = {loc}
            has_global_variable = {flag}
        }}
    }}'''
        text = replace_once(text, old, new, f"{je} complete")
    write_preserving_bom(p, text)


def fix_japanese_loc() -> None:
    p = ROOT / "localization/japanese/replace/toe_great_game_l_japanese.yml"
    text = p.read_text(encoding="utf-8-sig", errors="strict")
    replacements = {
        ' je_great_game_control_desc:0 "テーガール・ゴートン陣営とイルボネー・パイド陣営の勢力圏競争。進捗は100から開始し、イルボネー／パイド側の成功で増加、テーガール／ゴートン側の成功で減少する。130以上でイルボネー／パイド側の大勝利、70以下でテーガール／ゴートン側の大勝利となる。"':
        ' je_great_game_control_desc:0 "テーガール・ゴートン陣営とイルボネー・パイド陣営の世界規模の勢力圏競争。各国に表示される個別目標を達成し、グレートゲームの趨勢を自陣営へ引き寄せよ。"',
        ' je_toe_gg_steppe_desc:0 "大ステップ地域の6州以上を先に領有する。パイドが達成すれば進捗#p +20#!、ゴートンが達成すれば#n -20#!。イワジル（STATE_NSM_407）は分割州だが1州として数える。"':
        ' je_toe_gg_steppe_desc:0 "大ステップ地域の6州以上を先に領有する。イワジル（STATE_NSM_407）は分割州だが1州として数える。"',
        ' je_toe_gg_sosilia_desc:0 "ソシリアをパイドの属国とし、関係値50以上・独立欲求25以下にする。達成時、進捗#p +10#!。"':
        ' je_toe_gg_sosilia_desc:0 "ソシリアをパイドの属国とし、関係値50以上・独立欲求25以下にする。"',
        ' je_toe_gg_plains_desc:0 "大ジュズを完全に併合し、西亜22と西亜13をパイドが確保する。達成時、進捗#p +10#!。"':
        ' je_toe_gg_plains_desc:0 "大ジュズを完全に併合し、西亜22と西亜13をパイドが確保する。"',
        ' je_toe_gg_route_desc:0 "東欧86を直接征服するか、自国の属国または自国主導の勢力圏に入れる。イルボネー／パイド側なら進捗#p +25#!、テーガール／ゴートン側なら#n -25#!。"':
        ' je_toe_gg_route_desc:0 "東欧86を直接征服するか、自国の属国または自国主導の勢力圏に入れる。"',
        ' je_toe_gg_tegar_ria_desc:0 "セーロションを除くリイア大陸でテーガールが5州以上を直接領有する。達成時、進捗#n -25#!。"':
        ' je_toe_gg_tegar_ria_desc:0 "セーロションを除くリイア大陸でテーガールが5州以上を直接領有する。"',
        ' je_toe_gg_expel_tegar_ria_desc:0 "セーロションを含むリイア大陸から、テーガール本国・テーガールの属国・テーガール主導勢力圏による領有をすべて排除する。達成時、進捗#p +25#!。"':
        ' je_toe_gg_expel_tegar_ria_desc:0 "セーロションを含むリイア大陸から、テーガール本国・テーガールの属国・テーガール主導勢力圏による領有をすべて排除する。"',
        ' je_toe_gg_tortal_desc:0 "トルトルを自国の属国または自国主導の勢力圏に入れる。イルボネーなら進捗#p +15#!、テーガールなら#n -15#!。"':
        ' je_toe_gg_tortal_desc:0 "トルトルを自国の属国または自国主導の勢力圏に入れる。"',
        ' je_toe_gg_south_lefria_desc:0 "南レフリア地域で先に5州以上を直接領有する。イルボネーなら進捗#p +15#!、テーガールなら#n -15#!。"':
        ' je_toe_gg_south_lefria_desc:0 "南レフリア地域で先に5州以上を直接領有する。"',
    }
    for old, new in replacements.items():
        text = replace_once(text, old, new, old.split(':', 1)[0])
    write_preserving_bom(p, text)

    status = ROOT / "localization/japanese/replace/toe_great_game_status_l_japanese.yml"
    s = status.read_text(encoding="utf-8-sig", errors="strict")
    extra = '''
 toe_gg_ilvone_score_victory_tt:0 "イルボネー・パイド陣営：グレートゲームの趨勢が130以上"
 toe_gg_tegar_score_victory_tt:0 "テーガール・ゴートン陣営：グレートゲームの趨勢が70以下"
 toe_gg_steppe_complete_tt:0 "目標決着：パイド +20 ／ ゴートン -20"
 toe_gg_sosilia_complete_tt:0 "目標達成：パイド +10"
 toe_gg_plains_complete_tt:0 "目標達成：パイド +10"
 toe_gg_route_complete_tt:0 "目標決着：イルボネー・パイド +25 ／ テーガール・ゴートン -25"
 toe_gg_tegar_ria_complete_tt:0 "目標達成：テーガール -25"
 toe_gg_expel_complete_tt:0 "目標達成：イルボネー +25"
 toe_gg_tortal_complete_tt:0 "目標決着：イルボネー +15 ／ テーガール -15"
 toe_gg_south_lefria_complete_tt:0 "目標決着：イルボネー +15 ／ テーガール -15"
'''
    if "toe_gg_ilvone_score_victory_tt" in s:
        raise RuntimeError("Great Game condition localization already exists")
    s = s.rstrip() + "\n" + extra.lstrip("\n")
    write_preserving_bom(status, s)


def validate() -> None:
    geo = (ROOT / "common/scripted_triggers/00_geography_triggers.txt").read_text(encoding="utf-8-sig")
    for key in ("STATE_CALIFORNIA", "STATE_NEVADA", "STATE_ARIZONA", "STATE_UTAH", "STATE_LOWLANDS", "STATE_HIGHLANDS", "STATE_ULSTER", "STATE_LEINSTER", "STATE_CONNAUGHT", "STATE_MUNSTER"):
        if f"state_region = s:{key}" in geo:
            raise RuntimeError(f"vanilla drought state reference remains: {key}")

    parent = (ROOT / "common/journal_entries/00_player_objectives_great_game.txt").read_text(encoding="utf-8-sig")
    for je in SUBJOURNAL_SCORE_LOCS:
        if f"add_journal_entry = {{ type = {je} }}" not in parent:
            raise RuntimeError(f"sub-JE add call missing: {je}")
    if parent.count("change_global_variable = { name = toe_great_game_score") != 12:
        raise RuntimeError("Unexpected Great Game score-change count; baseline may be changing score")
    if "toe_gg_ilvone_score_victory_tt" not in parent or "toe_gg_tegar_score_victory_tt" not in parent:
        raise RuntimeError("custom completion score descriptions missing")

    sub = (ROOT / "common/journal_entries/99_toe_great_game_subjournals.txt").read_text(encoding="utf-8-sig")
    for loc in SUBJOURNAL_SCORE_LOCS.values():
        if f"text = {loc}" not in sub:
            raise RuntimeError(f"sub-JE condition tooltip missing: {loc}")

    loc = (ROOT / "localization/japanese/replace/toe_great_game_l_japanese.yml").read_text(encoding="utf-8-sig")
    if "達成時、進捗" in loc or "なら進捗#" in loc:
        raise RuntimeError("score text still remains in Great Game JE body descriptions")

    print("TOE_CRASH_GREAT_GAME_FIX_OK")


def main() -> None:
    fix_geography()
    fix_great_game_parent()
    fix_subjournal_conditions()
    fix_japanese_loc()
    validate()


if __name__ == "__main__":
    main()
