package cl.partescan.captura;

import android.content.Context;
import android.content.res.Configuration;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.graphics.drawable.Drawable;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Fluent 2 visual tokens, using Android's native Roboto type ramp and touch targets. */
final class FluentStyle {
    private final Context context;
    final boolean dark;
    final int background, surface, foreground, secondary, stroke, brand, onBrand, disabled, brandSubtle, danger;

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
        brandSubtle = color(dark ? "#082338" : "#EBF3FC");
        danger = color(dark ? "#F48771" : "#B10E1C");
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
    GradientDrawable panel() { return shape(surface, dark ? color("#424242") : color("#E0E0E0"), 12); }
    GradientDrawable selected() { return shape(brandSubtle, Color.TRANSPARENT, 8); }
    Drawable icon(int resource, int tint) {
        Drawable icon = context.getDrawable(resource).mutate();
        icon.setTint(tint);
        icon.setBounds(0, 0, dp(20), dp(20));
        return icon;
    }
    void interactive(View view, boolean selected) {
        view.setBackground(new RippleDrawable(ColorStateList.valueOf(dark ? 0x33FFFFFF : 0x160F6CBD),
                selected ? selected() : shape(Color.TRANSPARENT, Color.TRANSPARENT, 8), null));
        view.setFocusable(true);
        view.setClickable(true);
        view.setMinimumHeight(dp(48));
    }

    LinearLayout card(LinearLayout parent) {
        LinearLayout card = new LinearLayout(context);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(16), dp(16), dp(12));
        card.setBackground(panel());
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, -2);
        layout.topMargin = dp(12);
        layout.bottomMargin = dp(4);
        parent.addView(card, layout);
        return card;
    }

    void text(TextView view, int size) {
        view.setTextSize(size);
        view.setTextColor(size == 12 || size == 14 ? secondary : foreground);
        view.setTypeface(Typeface.create(size >= 20 ? "sans-serif-medium" : "sans-serif", Typeface.NORMAL));
        view.setLineSpacing(dp(4), 1f);
        view.setIncludeFontPadding(false);
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
        button.setGravity(Gravity.CENTER);
        GradientDrawable base = shape(fill, primary || !enabled ? Color.TRANSPARENT : stroke, 8);
        button.setBackground(new RippleDrawable(ColorStateList.valueOf(dark ? 0x33FFFFFF : 0x22000000),
                base, shape(Color.WHITE, Color.TRANSPARENT, 8)));
    }
}
