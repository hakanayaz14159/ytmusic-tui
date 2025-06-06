"""Custom theme for YTMusic CLI application."""

from textual.theme import Theme

# Create the YTMusic theme based on #81D4FA primary color
ytmusic_theme = Theme(
    name="ytmusic",
    primary="#81D4FA",  # Light blue - your primary color
    secondary="#FFB74D",  # Orange - complementary
    accent="#29B6F6",  # Darker blue - for accents
    warning="#FFA726",  # Orange warning
    error="#EF5350",  # Red error
    success="#66BB6A",  # Green success
    foreground="#F0F6FC",  # Light text
    background="#0D1117",  # Dark background
    surface="#21262D",  # Slightly lighter than background
    panel="#30363D",  # UI panels
    dark=True,  # This is a dark theme
    variables={
        # Custom scrollbar colors
        "scrollbar": "#30363D",
        "scrollbar-hover": "#484F58",
        "scrollbar-active": "#81D4FA",
        "scrollbar-background": "#161B22",
        # Custom border colors
        "border": "#81D4FA",
        "border-blurred": "#30363D",
        # Custom cursor colors
        "block-cursor-background": "#81D4FA",
        "block-cursor-foreground": "#0D1117",
        "block-cursor-text-style": "bold",
        "block-cursor-blurred-background": "#81D4FA40",  # 40% opacity
        # Input styling
        "input-cursor-background": "#F0F6FC",
        "input-cursor-foreground": "#0D1117",
        "input-selection-background": "#81D4FA40",
        # Footer styling
        "footer-foreground": "#F0F6FC",
        "footer-background": "#21262D",
        "footer-key-foreground": "#81D4FA",
        "footer-key-background": "transparent",
        # Button styling
        "button-foreground": "#F0F6FC",
        "button-color-foreground": "#0D1117",
        # Link styling
        "link-color": "#81D4FA",
        "link-color-hover": "#B3E7FC",
        "link-background-hover": "#81D4FA20",
    },
)
