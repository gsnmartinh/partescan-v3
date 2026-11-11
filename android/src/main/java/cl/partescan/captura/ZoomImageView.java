package cl.partescan.captura;

import android.content.Context;
import android.graphics.Matrix;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.widget.ImageView;

/** Vista de documentos con pellizco, arrastre y doble toque para restablecer. */
// La aplicación usa Activity y tema nativos en Android 9 o posterior.
@android.annotation.SuppressLint("AppCompatCustomView")
public final class ZoomImageView extends ImageView {
    private final Matrix matrix = new Matrix();
    private final ScaleGestureDetector scaleDetector;
    private final GestureDetector gestures;
    private float zoom = 1f;
    private float lastX, lastY;
    private boolean dragging;

    public ZoomImageView(Context context) {
        super(context);
        setScaleType(ScaleType.MATRIX);
        scaleDetector = new ScaleGestureDetector(context, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override public boolean onScale(ScaleGestureDetector detector) {
                float next = Math.max(1f, Math.min(6f, zoom * detector.getScaleFactor()));
                float factor = next / zoom;
                matrix.postScale(factor, factor, detector.getFocusX(), detector.getFocusY());
                zoom = next;
                setImageMatrix(matrix);
                return true;
            }
        });
        gestures = new GestureDetector(context, new GestureDetector.SimpleOnGestureListener() {
            @Override public boolean onDown(MotionEvent event) { return true; }
            @Override public boolean onDoubleTap(MotionEvent event) { fit(); return true; }
        });
        setContentDescription("Documento. Separa dos dedos para ampliar, arrastra para recorrer y toca dos veces para ajustar.");
    }

    private void fit() {
        if (getDrawable() == null || getWidth() == 0 || getHeight() == 0) return;
        float w = getDrawable().getIntrinsicWidth(), h = getDrawable().getIntrinsicHeight();
        float factor = Math.min(getWidth() / w, getHeight() / h);
        matrix.reset();
        matrix.postScale(factor, factor);
        matrix.postTranslate((getWidth() - w * factor) / 2, (getHeight() - h * factor) / 2);
        zoom = 1;
        setImageMatrix(matrix);
    }

    @Override protected void onSizeChanged(int w, int h, int oldW, int oldH) {
        super.onSizeChanged(w, h, oldW, oldH);
        fit();
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        scaleDetector.onTouchEvent(event);
        gestures.onTouchEvent(event);
        if (event.getPointerCount() == 1 && !scaleDetector.isInProgress()) {
            if (event.getActionMasked() == MotionEvent.ACTION_MOVE && dragging) {
                matrix.postTranslate(event.getX() - lastX, event.getY() - lastY);
                setImageMatrix(matrix);
            }
            lastX = event.getX(); lastY = event.getY();
            dragging = event.getActionMasked() != MotionEvent.ACTION_UP
                    && event.getActionMasked() != MotionEvent.ACTION_CANCEL;
        } else { dragging = false; }
        return true;
    }
}
