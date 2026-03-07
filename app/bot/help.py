"""Help message for new users and /help."""

HELP_MESSAGE = """Welcome to the BRVM Stock Assistant.

This bot helps you with the BRVM (Bourse Régionale des Valeurs Mobilières) stock market. All prices are in F CFA.

What you can do:

• Ask for prices: "What is the price of NTLC?" or "Compare NTLC and SLBC"
• Market overview: "Most traded stock on BRVM?" or "Top gainers"
• Charts: "Plot NTLC from 2025-01-01 to 2025-02-21"
• News: "Latest news about Sonatel" or "BRVM market news"
• BRVM basics: "What is BRVM?" or "How to invest on BRVM?"

Portfolio and alerts (your personal data):

• Portfolio: "Show my portfolio" / "Add NTLC to my portfolio: bought at 50000 on 2025-01-15" / "Remove NTLC from my portfolio" / "Portfolio growth"
• Tracking: "Add NTLC to my tracking list" / "What am I tracking?" / "Remove NTLC from tracking"
• Price alerts: "Notify me when NTLC reaches 55000" / "My price targets" / "Remove alert for NTLC"

• Clear conversation memory: send /clearmemory to delete the bot's memory of this chat and start fresh.

You can type or send a voice message. Say "help" anytime to see this message again."""


def get_help_message() -> str:
    return HELP_MESSAGE.strip()
