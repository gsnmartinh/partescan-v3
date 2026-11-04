package cl.partescan.captura;

import android.content.Context;
import android.content.res.Configuration;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Fluent 2 visual tokens, using Android's native Roboto type ramp and touch targets. */
final class FluentStyle {
    private final Context context;
    final boolean dark;
    final int background, surface, foreground, secondary, stroke, brand, onBrand, disabled;

    FluentStyle(Context context) {
        this.context = context;
        dark = (context.getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)
                == Configuration.UI_MODE_NIGHT_YES;
        background = color(dark ? "#1F1F1F" : "#F5F5F5");
        surface = color(dark ? "#292929" : "#FFFFFF");
        foreground = color(dark ? "#FFFFFF" : "#242424");
        secondary = color(dark ? "#ADADAD" : "#616161");
        stroke = color(dark ? "#666666" : "#D1D1D1");
        brand = color(dark ? "#479EF5" : "#0F6CBD");
        onBrand = color(dark ? "#0A0A0A" : "#FFFFFF");
        disabled = color(dark ? "#424242" : "#E0E0E0");
    }

    private static int color(String hex) { return Color.parseColor(hex); }
    int dp(int value) { return Math.round(value * context.getResources().getDisplayMetrics().density); }

    private GradientDrawable shape(int fill, int border, int radius) {
        GradientDrawable result = new GradientDrawable();
        result.setColor(fill);
        result.setCornerRadius(dp(radius));
        if (border != Color.TRANSPARENT) result.setStroke(dp(1), border);
        return result;
    }

    GradientDrawable surface() { return shape(background, Color.TRANSPARENT, 8); }

    LinearLayout card(LinearLayout parent) {
        LinearLayout card = new LinearLayout(context);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(16), dp(16), dp(12));
        card.setBackground(shape(surface, dark ? color("#424242") : color("#E0E0E0"), 12));
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, -2);
        layout.topMargin = dp(12);
        layout.bottomMargin = dp(4);
        parent.addView(card, layout);
        return card;
    }

    void text(TextView view, int size) {
        view.setTextSize(size);
        view.setTextColor(size == 12 || size == 14 ? secondary : foreground);
        view.setTypeface(Typeface.create(size >= 20 || size == 12 ? "sans-serif-medium" : "sans-serif", Typeface.NORMAL));
        view.setLineSpacing(dp(4), 1f);
        view.setIncludeFontPadding(false);
        if (size == 12) view.setLetterSpacing(.08f);
    }

    void button(Button button, boolean primary, boolean enabled) {
        button.setAllCaps(false);
        button.setTextSize(14);
        button.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        button.setMinHeight(dp(48));
        button.setMinimumHeight(dp(48));
        button.setPadding(dp(16), dp(10), dp(16), dp(10));
        button.setStateListAnimator(null);
        button.setElevation(0);
        int fill = !enabled ? background : primary ? brand : surface;
        button.setTextColor(!enabled ? secondary : primary ? onBrand : foreground);
        GradientDrawable base = shape(fill, primary || !enabled ? Color.TRANSPARENT : stroke, 4);
        button.setBackground(new RippleDrawable(ColorStateList.valueOf(dark ? 0x33FFFFFF : 0x22000000),
                base, shape(Color.WHITE, Color.TRANSPARENT, 4)));
    }
}
