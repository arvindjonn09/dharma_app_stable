import datetime
import json
import os
import streamlit as st
from security_utils import encrypt_field, decrypt_field


def load_feedback(feedback_file: str):
    try:
        with open(feedback_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            cleaned = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                item = dict(item)
                item["text"] = decrypt_field(item.get("text") or "")
                item["contact"] = decrypt_field(item.get("contact") or "")
                cleaned.append(item)
            return cleaned
        return []
    except FileNotFoundError:
        return []
    except Exception:
        return []


def save_feedback(feedback_file: str, items):
    try:
        to_store = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            copy_item = dict(item)
            copy_item["text"] = encrypt_field(copy_item.get("text") or "")
            copy_item["contact"] = encrypt_field(copy_item.get("contact") or "")
            to_store.append(copy_item)
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump(to_store, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_daily_reflection(age_group, daily_reflection_file: str):
    """
    Return a tuple of (text, image_url) for the day.
    Supports legacy string-only entries.
    """
    overrides = {}
    try:
        with open(daily_reflection_file, "r", encoding="utf-8") as f:
            overrides = json.load(f)
    except Exception:
        overrides = {}

    def _extract(val):
        if isinstance(val, dict):
            return val.get("text"), val.get("image_url")
        return val, None

    if isinstance(overrides, dict):
        if age_group == "child" and overrides.get("child"):
            return _extract(overrides["child"])
        if age_group == "adult" and overrides.get("adult"):
            return _extract(overrides["adult"])
        if overrides.get("both"):
            return _extract(overrides["both"])

    adult_reflections = [
        "Pause once today and remember: every small act of kindness can be placed at the Lord's feet like a flower.",
        "When the mind becomes restless, gently return to the breath and recall one quality of your chosen deity.",
        "Before sleep, think of one moment today where you could have been softer. Offer that moment into inner light.",
        "Wherever you are today, imagine you are standing in a sacred space. Speak and act as if the Divine is listening.",
        "If worry arises, quietly say: 'I am not alone in this. May I act with dharma and trust.'",
    ]

    child_reflections = [
        "Can you share something today and imagine you are sharing it with God?",
        "If you feel angry today, take three slow breaths and think of your favourite form of the Divine smiling at you.",
        "Try to tell the truth today even in small things. Saints smile when you are honest.",
        "Before you sleep, thank the Divine for one happy moment from your day.",
        "When you see someone sad today, can you say one kind word for them in your heart?",
    ]

    today = datetime.date.today()
    idx = today.toordinal()

    if age_group == "child":
        items = child_reflections
    else:
        items = adult_reflections

    return items[idx % len(items)], None


def get_daily_focus(age_group):
    themes = [
        "Remembering one divine quality again and again.",
        "Bringing kindness into one small action.",
        "Watching the breath for a few quiet moments.",
        "Offering worries into an inner flame of trust.",
        "Seeing every being as carrying a spark of the Divine.",
    ]
    today = datetime.date.today()
    idx = today.toordinal()
    line = themes[idx % len(themes)]
    if age_group == "child":
        child_variants = [
            "Remember one good thing about God again and again today.",
            "Try one extra kind action today.",
            "Close your eyes and feel 5 soft breaths.",
            "Give one worry to God in your heart.",
            "Look at people and think: 'There is a little light inside them.'",
        ]
        line = child_variants[idx % len(child_variants)]
    return line


def get_micro_practice(age_group):
    adult_items = [
        "Before checking your phone in the morning, place your hand on your heart and remember your chosen deity once.",
        "Take 3 conscious breaths before starting any important task today.",
        "When irritation arises, pause for one breath and silently repeat a divine name once.",
        "Before sleep, mentally offer the best and worst moments of your day into a small inner flame.",
        "Choose one action today and consciously dedicate it as a small offering.",
    ]
    child_items = [
        "Say thank you to God once today in your own words.",
        "Take 3 slow breaths and imagine light in your heart.",
        "When you feel angry, count to 5 and think of your favourite form of God.",
        "Before sleep, tell the Divine one thing you liked today.",
        "Share one toy or snack and imagine the Divine smiling.",
    ]
    today = datetime.date.today()
    idx = today.toordinal()
    if age_group == "child":
        return child_items[idx % len(child_items)]
    else:
        return adult_items[idx % len(adult_items)]


def get_current_username():
    profile = st.session_state.get("user_profile") or {}
    return profile.get("username") or st.session_state.get("user_name")
