import spacy
from spacy.matcher import PhraseMatcher

# Load English tokenizer, POS tagger, etc.
nlp = spacy.load("en_core_web_sm")

# Define keyword sets for user preference matching
summary_lengths = {
    "short": [
        "short", "brief", "quick", "tiny", "tiny summary", "bite-sized", "one-liner",
        "small", "few lines", "1 para", "just the gist", "minimal", "mini", "fast read"
    ],
    "medium": [
        "medium", "moderate", "normal", "standard", "average size", "not too long", 
        "decent", "mid-size", "middle-ish", "some detail", "balanced", "regular"
    ],
    "detailed": [
        "detailed", "comprehensive", "elaborate", "in-depth", "extensive", 
        "full story", "long", "complete", "verbose", "thorough", 
        "everything", "all info", "explain everything", "lengthy"
    ]
}

styles = {
    "bullets": [
        "bullets", "bullet points", "point-wise", "points", "dot points", 
        "key pts", "key points", "• style", "style", "summarized points", 
        "no para", "list form", "structured bullets"
    ],
    "paragraph": [
        "paragraph", "text block", "essay", "long text", "normal para", 
        "proper text", "write it out", "explain in para", "continuous", 
        "elaborate text", "write properly", "para style"
    ],
    "highlights": [
        "highlight", "highlighted", "key takeaways", "tl;dr", "tldr", 
        "main ideas", "main summary", "glance view", "recap", 
        "summary points", "highlight stuff", "bold points"
    ]
}

language_levels = {
    "simple": [
        "simple", "easy", "basic", "plain", "casual", "layman", "beginner", 
        "dumb it down", "explain like im 5", "no jargon", "simplified", 
        "baby level", "not too technical", "in easy terms", "easy"
    ],
    "intermediate": [
        "intermediate", "moderate", "average", "mid-level", "some jargon", 
        "normal wording", "standard", "balanced level", "medium difficulty"
    ],
    "advanced": [
        "advanced", "complex", "technical", "expert", "academic", "pro level", 
        "intellectual", "smart wording", "detailed language", "jargon allowed", 
        "not basic", "professional style", "industry-level", "smarter"
    ]
}

# Helper to prepare phrase matcher
def build_matcher(nlp, keyword_dict):
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    for label, phrases in keyword_dict.items():
        matcher.add(label, [nlp(text) for text in phrases])
    return matcher

# Create matchers for all categories
length_matcher = build_matcher(nlp, summary_lengths)
style_matcher = build_matcher(nlp, styles)
level_matcher = build_matcher(nlp, language_levels)

# Default preferences
DEFAULT_PREFS = {
    "summary_length": "medium",
    "style": "paragraph",
    "language_level": "intermediate"
}

def is_pref(user_input):
    """
    Checks if user input is a preference or not.
    """
    doc = nlp(user_input)

    preference_keywords = (
        summary_lengths["short"] + summary_lengths["medium"] + summary_lengths["detailed"] +
        styles["bullets"] + styles["paragraph"] + styles["highlights"] +
        language_levels["simple"] + language_levels["intermediate"] + language_levels["advanced"] +
        ["summarize", "summarise", "make it", "i want", "please", "format", "language level", "tone", "style"]
    )

    # NLP-based heuristic: check for imperative verbs, direct intent, and keyword overlap
    preference_score = 0

    for token in doc:
        if token.text.lower() in preference_keywords:
            preference_score += 1
        if token.dep_ == "ROOT" and token.tag_ == "VB":  # imperative form like "Make", "Use"
            preference_score += 1
        if token.lemma_ in ["want", "prefer", "need", "like"]:
            preference_score += 1

    if preference_score >= 2:  # Arbitrary threshold for preference detection
        return preference_score
    return False

# Main function
def extract_summary_preferences(user_input):
    if user_input.split() == []:
        return {
            **DEFAULT_PREFS,
            "custom_message": "Using default summary settings. You can type your preferences anytime!"
        }
    elif len(user_input.split()) < 3:
        return {
            **DEFAULT_PREFS,
            "custom_message": "Please provide more details for better summary preferences."
        }
    elif not is_pref(user_input):
        return {
            **DEFAULT_PREFS,
            "custom_message": "Please provide more details for better summary preferences."
        }

    doc = nlp(user_input)
    prefs = DEFAULT_PREFS.copy()
    msg_parts = []

    # Match summary length
    length_matches = length_matcher(doc)
    if length_matches:
        label = nlp.vocab.strings[length_matches[0][0]]
        prefs["summary_length"] = label
        msg_parts.append(f"{label} summary")

    # Match style
    style_matches = style_matcher(doc)
    if style_matches:
        label = nlp.vocab.strings[style_matches[0][0]]
        prefs["style"] = label
        msg_parts.append(f"in {label.replace('_', ' ')} format")

    # Match language level
    level_matches = level_matcher(doc)
    if level_matches:
        label = nlp.vocab.strings[level_matches[0][0]]
        prefs["language_level"] = label
        msg_parts.append(f"using {label} language")

    # Create chatbot response
    if msg_parts:
        response = f"Got it! I'll generate a {' '.join(msg_parts)}."
    else:
        response = "Using default summary settings. You can type your preferences anytime!"

    return {
        **prefs,
        "custom_message": response
    }

# Test example
# user_texts = [
#     "This is a brief overview of the Cold War, covering the key events in a simple format that even beginners can understand.",
#     "In-depth research has shown that simple sugars can have complex effects on human metabolism over time.",
#     "The author presents the theory in bullet points to simplify explanation, but each point is quite detailed.",
#     "Simple instructions were given to soldiers during the battle, but executing them was far from easy.",
#     "This document is divided into sections: the first being a quick introduction, the second a deep analysis, and the third a critique.",
#     "Key points from the article include health, education, and climate reform, which are elaborated in the main body.",
#     "Students often prefer one paragraph summaries, but the professor required a ten-page analysis.",
#     "He gave a highlight of the economic reforms during the session, but the rest of the speech was ignored.",
#     "Though the book appears academic, the underlying tone is surprisingly sarcastic and informal.",
#     "Short-term effects of the medicine include fatigue and nausea, while long-term data is still being collected."
# ]

