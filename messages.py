"""SMS wording. Neutral: never name a disease. The Sesotho text is a DRAFT: have a native speaker review it."""
MSG = {
    "en": "Hello {n}. Your clinic visit is on {d}. Please come. Reply 1 if coming, 2 to change the day, 0 to stop messages.",
    "st": "Lumela {n}. Ho etela kliniki ha hau ke ka {d}. Ka kopo tla. Araba 1 haeba u tla, 2 ho fetola letsatsi, 0 ho emisa melaetsa.",
}


def reminder_text(lang, name, day):
    return MSG.get(lang, MSG["en"]).format(n=name, d=day)
