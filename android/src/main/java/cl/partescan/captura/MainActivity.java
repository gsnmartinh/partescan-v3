package cl.partescan.captura;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.ImageDecoder;
import android.graphics.RectF;
import android.graphics.pdf.PdfDocument;
import android.os.Bundle;
import android.provider.MediaStore;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import androidx.core.content.FileProvider;
import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.UUID;

public class MainActivity extends Activity {
    private File folder;
    private final ArrayList<String> pages = new ArrayList<>();
    private int completedParts;
    private String part;
    private String certificate;
    private String pending;
    private static final int PART = 1, CERTIFICATE = 2, SAVE = 3, NEXT = 4;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        folder = new File(getCacheDir(), "capturas");
        folder.mkdirs();
        if (state != null) {
            ArrayList<String> savedPages = state.getStringArrayList("pages");
            if (savedPages != null) pages.addAll(savedPages);
            completedParts = state.getInt("completedParts");
            part = state.getString("part");
            certificate = state.getString("certificate");
            pending = state.getString("pending");
        }
        render("");
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        state.putStringArrayList("pages", new ArrayList<>(pages));
        state.putInt("completedParts", completedParts);
        state.putString("part", part);
        state.putString("certificate", certificate);
        state.putString("pending", pending);
    }

    private void render(String message) {
        ScrollView scroll = new ScrollView(this);
        scroll.setFitsSystemWindows(true);
        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        int padding = Math.round(20 * getResources().getDisplayMetrics().density);
        body.setPadding(padding, padding, padding, padding);
        scroll.addView(body);
        setContentView(scroll);
        label(body, "ParteScan Captura", 26);
        label(body, "Fotografía cualquier tipo de parte. Agrega el certificado si corresponde.", 16);
        int count = completedParts + (part == null ? 0 : 1);
        label(body, "Partes en la tanda: " + count, 18);
        if (part != null) label(body, "Parte " + (completedParts + 1), 16);
        button(body, part == null ? "Escanear parte" : "Repetir foto del parte", true, () -> capture(PART));
        preview(body, part, "Foto del parte");
        button(body, certificate == null ? "Agregar certificado (opcional)" : "Repetir foto del certificado",
                part != null, () -> capture(CERTIFICATE));
        preview(body, certificate, "Foto del certificado");
        if (certificate != null) {
            button(body, "Quitar certificado", true, () -> {
                delete(certificate);
                certificate = null;
                render("");
            });
        }
        button(body, "Siguiente parte", part != null, () -> capture(NEXT));
        button(body, "Guardar tanda", count > 0, this::save);
        button(body, "Nueva tanda", count > 0, () ->
            new android.app.AlertDialog.Builder(this)
                .setMessage("¿Borrar las capturas de esta tanda?")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Nueva tanda", (dialog, which) -> {
                    for (String page : pages) delete(page);
                    pages.clear();
                    completedParts = 0;
                    delete(part);
                    delete(certificate);
                    part = certificate = null;
                    render("");
                }).show());
        label(body, message, 16);
    }

    private void label(LinearLayout body, String text, int size) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(size);
        body.addView(view);
    }

    private void button(LinearLayout body, String text, boolean enabled, Runnable action) {
        Button button = new Button(this);
        button.setText(text);
        button.setEnabled(enabled);
        button.setOnClickListener(view -> action.run());
        body.addView(button);
    }

    private void preview(LinearLayout body, String name, String description) {
        if (name == null) return;
        try {
            ImageView view = new ImageView(this);
            view.setContentDescription(description);
            view.setImageBitmap(decode(name, 500));
            int height = Math.round(210 * getResources().getDisplayMetrics().density);
            body.addView(view, ViewGroup.LayoutParams.MATCH_PARENT, height);
        } catch (IOException error) {
            label(body, "La foto ya no está disponible. Repite la captura.", 16);
        }
    }

    private Bitmap decode(String name, int limit) throws IOException {
        return ImageDecoder.decodeBitmap(ImageDecoder.createSource(new File(folder, name)),
            (decoder, info, source) -> {
                int width = info.getSize().getWidth();
                int height = info.getSize().getHeight();
                double scale = Math.min(1.0, (double) limit / Math.max(width, height));
                decoder.setTargetSize(Math.max(1, (int) (width * scale)),
                        Math.max(1, (int) (height * scale)));
                decoder.setAllocator(ImageDecoder.ALLOCATOR_SOFTWARE);
            });
    }

    private void capture(int type) {
        pending = UUID.randomUUID() + ".jpg";
        File file = new File(folder, pending);
        try {
            if (!file.createNewFile()) throw new IOException();
            android.net.Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".fotos", file);
            Intent camera = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
            camera.putExtra(MediaStore.EXTRA_OUTPUT, uri);
            camera.setClipData(ClipData.newRawUri("captura", uri));
            camera.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            startActivityForResult(camera, type);
        } catch (IOException | RuntimeException error) {
            delete(pending);
            pending = null;
            render("No se pudo abrir la cámara.");
        }
    }

    private void save() {
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.setType("application/pdf");
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.putExtra(Intent.EXTRA_LOCAL_ONLY, true);
        String date = new java.text.SimpleDateFormat("yyyyMMdd-HHmmss", java.util.Locale.ROOT)
                .format(new java.util.Date());
        intent.putExtra(Intent.EXTRA_TITLE, "ParteScan-" + date + ".pdf");
        try {
            startActivityForResult(intent, SAVE);
        } catch (RuntimeException error) {
            render("No se pudo abrir el selector de archivos.");
        }
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == PART || request == CERTIFICATE || request == NEXT) {
            String captured = pending;
            pending = null;
            if (captured == null) return;
            if (result != RESULT_OK || new File(folder, captured).length() == 0) {
                delete(captured);
                render("No se guardó una foto nueva.");
                return;
            }
            if (request == NEXT) {
                pages.add(part);
                if (certificate != null) pages.add(certificate);
                completedParts++;
                part = captured;
                certificate = null;
            } else if (request == PART) {
                delete(part);
                part = captured;
            } else {
                delete(certificate);
                certificate = captured;
            }
            render("");
        } else if (request == SAVE && result == RESULT_OK && data != null && data.getData() != null) {
            PdfDocument pdf = new PdfDocument();
            try {
                int pageNumber = 1;
                for (String page : pages) addPage(pdf, page, pageNumber++);
                if (part != null) addPage(pdf, part, pageNumber++);
                if (certificate != null) addPage(pdf, certificate, pageNumber);
                try (OutputStream output = getContentResolver().openOutputStream(data.getData())) {
                    if (output == null) throw new IOException();
                    pdf.writeTo(output);
                }
                render("Tanda guardada. Copia el PDF al PC por USB y ábrelo en ParteScan.");
            } catch (IOException | RuntimeException error) {
                render("No se pudo guardar el PDF. Puedes intentarlo nuevamente.");
            } finally {
                pdf.close();
            }
        }
    }

    private void addPage(PdfDocument pdf, String name, int number) throws IOException {
        Bitmap bitmap = decode(name, 3000);
        boolean landscape = bitmap.getWidth() > bitmap.getHeight();
        int width = landscape ? 842 : 595;
        int height = landscape ? 595 : 842;
        PdfDocument.Page page = pdf.startPage(new PdfDocument.PageInfo.Builder(width, height, number).create());
        float scale = Math.min((float) width / bitmap.getWidth(), (float) height / bitmap.getHeight());
        float x = (width - bitmap.getWidth() * scale) / 2;
        float y = (height - bitmap.getHeight() * scale) / 2;
        page.getCanvas().drawBitmap(bitmap, null,
                new RectF(x, y, width - x, height - y), new android.graphics.Paint(android.graphics.Paint.FILTER_BITMAP_FLAG));
        pdf.finishPage(page);
    }

    private void delete(String name) {
        if (name != null) new File(folder, name).delete();
    }
}
