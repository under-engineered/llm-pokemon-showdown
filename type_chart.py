TYPES = [
    "Normal",
    "Fighting",
    "Flying",
    "Poison",
    "Ground",
    "Rock",
    "Bug",
    "Ghost",
    "Steel",
    "Fire",
    "Water",
    "Grass",
    "Electric",
    "Psychic",
    "Ice",
    "Dragon",
    "Dark",
    "Fairy",
    "Stellar"
]

def determine_effectiveness(attacker_type: str, defender_type1: str, defender_type2: str) -> float:
    effectiveness = 1.0
    effectiveness *= type_chart(attacker_type, defender_type1)
    effectiveness *= type_chart(attacker_type, defender_type2)
    
    if effectiveness == 0.0:
        return "Will do nothing"
    elif effectiveness == 0.25:
        return "Very Resisted, will do quarter damage"
    elif effectiveness == 0.5:
        return "Resisted, will do half damage"
    elif effectiveness == 1.0:
        return "Will do normal amount of damage"
    elif effectiveness == 2.0:
        return "Will be super effective (2x damage)"
    elif effectiveness == 4.0:
        return "Will be very very effective (4x damage)"
    
    return "Will do normal amount of damage"

def type_chart(attack_type: str, defend_type: str):
    match (attack_type):
        case "Normal":
            match (defend_type):
                case "Ghost":
                    return 0.0
                case "Steel" | "Rock":
                    return 0.5
                case _:
                    return 1.0
        case "Fire":
            match (defend_type):
                case "Fire" | "Water" | "Rock" | "Dragon":
                    return 0.5
                case "Steel" | "Grass" | "Ice" | "Bug":
                    return 2.0
                case _:
                    return 1.0
        case "Water":
            match (defend_type):
                case "Water" | "Grass" | "Dragon":
                    return 0.5
                case "Fire" | "Rock" | "Ground":
                    return 2.0
                case _:
                    return 1.0
        case "Grass":
            match (defend_type):
                case "Fire" | "Grass" | "Dragon" | "Poison" | "Flying" | "Bug" | "Steel":
                    return 0.5
                case "Water" | "Ground" | "Rock":
                    return 2.0
                case _:
                    return 1.0
        case "Electric":
            match (defend_type):
                case "Water" | "Flying":
                    return 2.0
                case "Grass" | "Dragon" | "Electric":
                    return 0.5
                case "Ground":
                    return 0.0
                case _:
                    return 1.0
        case "Ice":
            match (defend_type):
                case "Fire" | "Water" | "Ice" | "Steel":
                    return 0.5
                case "Grass" | "Ground" | "Flying" | "Dragon":
                    return 2.0
                case _:
                    return 1.0
        case "Fighting":
            match (defend_type):
                case "Normal" | "Rock" | "Steel" | "Dark" | "Ice":
                    return 2.0
                case "Flying" | "Poison" | "Psychic" | "Bug" | "Fairy":
                    return 0.5
                case "Ghost":
                    return 0.0
                case _:
                    return 1.0
        case "Poison":
            match (defend_type):
                case "Grass" | "Fairy":
                    return 2.0
                case "Poison" | "Ground" | "Rock" | "Ghost":
                    return 0.5
                case "Steel":
                    return 0.0
                case _:
                    return 1.0
        case "Ground":
            match (defend_type):
                case "Grass" | "Bug":
                    return 0.5
                case "Fire" | "Electric" | "Poison" | "Rock" | "Steel":
                    return 2.0
                case "Flying":
                    return 0.0
                case _:
                    return 1.0
        case "Flying":
            match (defend_type):
                case "Grass" | "Fighting" | "Bug":
                    return 2.0
                case "Rock" | "Steel" | "Electric":
                    return 0.5
                case _:
                    return 1.0
        case "Psychic":
            match (defend_type):
                case "Fighting" | "Poison":
                    return 2.0
                case "Psychic" | "Steel":
                    return 0.5
                case "Dark":
                    return 0.0
                case _:
                    return 1.0
        case "Bug":
            match (defend_type):
                case "Grass" | "Psychic" | "Dark":
                    return 2.0
                case "Fire" | "Fighting" | "Poison" | "Flying" | "Ghost" | "Steel" | "Fairy":
                    return 0.5
                case _:
                    return 1.0
        case "Ghost":
            match (defend_type):
                case "Ghost" | "Psychic":
                    return 2.0
                case "Dark":
                    return 0.5
                case "Normal":
                    return 0.0
                case _:
                    return 1.0
        case "Dragon":
            match (defend_type):
                case "Dragon":
                    return 2.0
                case "Steel":
                    return 0.5
                case "Fairy":
                    return 0.0
                case _:
                    return 1.0
        case "Dark":
            match (defend_type):
                case "Ghost" | "Psychic":
                    return 2.0
                case "Fighting" | "Dark" | "Fairy":
                    return 0.5
                case _:
                    return 1.0
        case "Steel":
            match (defend_type):
                case "Ice" | "Rock" | "Fairy":
                    return 2.0
                case "Steel" | "Fire" | "Water" | "Electric":
                    return 0.5
                case _:
                    return 1.0
        case "Fairy":
            match (defend_type):
                case "Fighting" | "Dragon" | "Dark":
                    return 2.0
                case "Poison" | "Steel":
                    return 0.5
                case _:
                    return 1.0
        case _:
            return 1.0
