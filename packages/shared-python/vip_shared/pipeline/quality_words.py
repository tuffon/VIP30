"""Centralized prohibited language lists for deterministic quality gates."""

# GATE-01: hedge/speculative language and weak assertion terms.
HEDGE_WORDS: list[str] = [
    "appears", "seems", "might", "may", "could", "possibly", "potentially",
    "suggests", "indicates", "perhaps", "likely", "probably", "apparently",
    "presumably", "arguably", "conceivably", "plausibly", "ostensibly",
    "purportedly", "allegedly", "supposedly", "roughly", "approximately",
    "estimated", "ballpark", "assumed", "about", "around", "near",
    "seemingly", "apparently", "putatively", "conceivably", "tentatively",
    "it would appear", "one might argue", "it could be said",
    "there is reason to believe", "it stands to reason", "in all likelihood",
    "for all intents and purposes", "in the range of", "on the order of",
    "may indicate", "likely due to", "appears to be", "seems to suggest",
    "could potentially", "might be attributed to", "possibly due to",
    "suggests that", "this indicates that", "this suggests",
    "may have caused", "could have resulted", "might be attributed",
    "possibly attributable", "appears to be caused by", "seems to indicate",
]

# GATE-01: AI-slop phrases (kept under GATE-01 umbrella by plan).
SLOP_PHRASES: list[str] = [
    "delve", "tapestry", "landscape", "comprehensive", "holistic",
    "leverage", "synergy", "significantly", "ultimately", "essentially",
    "arguably", "undoubtedly", "furthermore", "moreover", "nevertheless",
    "paradigm", "robust", "streamline", "optimize", "seamless",
    "it's worth noting", "it is worth noting",
    "it is important to", "it's important to",
    "in conclusion", "at the end of the day",
    "moving forward", "in order to",
    "a testament to", "serves as a reminder",
    "a myriad of", "a plethora of",
    "dive into", "dive deep",
    "as we navigate", "navigating the",
]

# GATE-02: evaluative adjectives/terms that create advocacy tone.
JUDGMENT_ADJECTIVES: list[str] = [
    "excessive", "inadequate", "inflated", "deflated", "unreasonable", "reasonable",
    "appropriate", "inappropriate", "sufficient", "insufficient", "overestimated",
    "underestimated", "overstated", "understated", "exaggerated", "minimized",
    "thorough", "sloppy", "careless", "meticulous", "negligent", "incomplete",
    "deficient", "superior", "inferior", "correct", "incorrect", "accurate",
    "inaccurate", "wrong", "right", "proper", "improper", "valid", "invalid",
    "legitimate", "illegitimate", "necessary", "unnecessary", "essential",
    "nonessential", "required", "unwarranted", "justified", "unjustified",
    "fair", "unfair", "generous", "stingy", "padded", "gutted", "bloated",
    "lean", "aggressive", "conservative", "lowball", "lowballed", "shortchanged",
    "gouging", "overscoped", "underscoped", "best", "worst", "optimal", "suboptimal",
]

# GATE-02: advocacy phrases that imply side-taking.
JUDGMENT_PHRASES: list[str] = [
    "fails to adequately", "does not properly", "should have included",
    "should not have included", "fails to account for", "neglects to include",
    "overlooks the need for", "ignores the requirement", "the correct approach",
    "the proper method", "industry standard requires", "best practices dictate",
    "any competent adjuster", "a reasonable adjuster would", "clearly demonstrates",
    "obviously shows", "full extent of necessary work",
    "fails to capture the true cost", "clearly overstates", "clearly understates",
]

# GATE-05: prohibited comparative/standard-referencing methodology language.
METHODOLOGY_PROHIBITED: list[str] = [
    "better", "worse", "superior", "inferior", "more accurate", "less accurate",
    "more appropriate", "less appropriate", "more thorough", "less thorough",
    "more reliable", "less reliable", "preferred", "recommended", "best",
    "industry standard", "best practice", "accepted practice", "standard methodology",
    "proper methodology", "correct methodology", "appropriate methodology",
    "recognized approach", "preferred approach", "recommended approach",
    "fails to comply", "does not meet standards", "non-compliant", "substandard",
    "below industry norms", "does not conform", "not up to standard", "gold standard",
]
