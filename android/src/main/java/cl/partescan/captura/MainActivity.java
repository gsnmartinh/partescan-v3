package cl.partescan.captura;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.ImageDecoder;
import android.graphics.Rect;
import android.graphics.Point;
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
import java.util.Comparator;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONArray;
import org.json.JSONObject;
import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

public class MainActivity extends Activity {
    private File folder;
    private final ArrayList<String> pages = new ArrayList<>();
    private final ArrayList<Integer> attachments = new ArrayList<>();
    private int completedParts;
    private String part;
    private String certificate;
    private String pending;
    private static final int PART = 1, CERTIFICATE = 2, SAVE = 3, NEXT = 4, SAVE_OCR = 5;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        folder = new File(getCacheDir(), "capturas");
        folder.mkdirs();
        if (state != null) {
            ArrayList<String> savedPages = state.getStringArrayList("pages");
            if (savedPages != null) pages.addAll(savedPages);
            ArrayList<Integer> savedAttachments = state.getIntegerArrayList("attachments");
            if (savedAttachments != null) attachments.addAll(savedAttachments);
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
        state.putIntegerArrayList("attachments", new ArrayList<>(attachments));
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
        button(body, "Guardar tanda con OCR", count > 0, () -> save(true));
        button(body, "Guardar PDF", count > 0, () -> save(false));
        button(body, "Nueva tanda", count > 0, () ->
            new android.app.AlertDialog.Builder(this)
                .setMessage("¿Borrar las capturas de esta tanda?")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Nueva tanda", (dialog, which) -> {
                    for (String page : pages) delete(page);
                    pages.clear();
                    attachments.clear();
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

    private void save(boolean ocr) {
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.setType(ocr ? "application/octet-stream" : "application/pdf");
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.putExtra(Intent.EXTRA_LOCAL_ONLY, true);
        String date = new java.text.SimpleDateFormat("yyyyMMdd-HHmmss", java.util.Locale.ROOT)
                .format(new java.util.Date());
        intent.putExtra(Intent.EXTRA_TITLE, "ParteScan-" + date + (ocr ? ".psocr" : ".pdf"));
        try {
            startActivityForResult(intent, ocr ? SAVE_OCR : SAVE);
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
                if (certificate != null) {
                    attachments.add(pages.size());
                    pages.add(certificate);
                }
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
        } else if (request == SAVE_OCR && result == RESULT_OK && data != null && data.getData() != null) {
            exportOcr(data.getData());
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

    private void exportOcr(android.net.Uri destination) {
        ArrayList<String> photos = new ArrayList<>(pages);
        ArrayList<Integer> certificates = new ArrayList<>(attachments);
        if (part != null) photos.add(part);
        if (certificate != null) {
            certificates.add(photos.size());
            photos.add(certificate);
        }
        TextView progress = new TextView(this);
        progress.setText("Reconociendo texto en el teléfono…");
        setContentView(progress);
        new Thread(() -> {
            String message;
            TextRecognizer reader = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            try {
                JSONArray manifest = new JSONArray();
                for (int i = 0; i < photos.size(); i++) {
                    Bitmap bitmap = decode(photos.get(i), 3000);
                    String text;
                    try {
                        text = orderedText(Tasks.await(reader.process(InputImage.fromBitmap(bitmap, 0))));
                    } finally {
                        bitmap.recycle();
                    }
                    manifest.put(new JSONObject().put("texto", text)
                        .put("certificado", certificates.contains(i)));
                }
                try (OutputStream stream = getContentResolver().openOutputStream(destination);
                     ZipOutputStream zip = new ZipOutputStream(stream)) {
                    zip.putNextEntry(new ZipEntry("ocr.json"));
                    zip.write(manifest.toString().getBytes(StandardCharsets.UTF_8));
                    zip.closeEntry();
                    for (int i = 0; i < photos.size(); i++) {
                        zip.putNextEntry(new ZipEntry(i + ".jpg"));
                        java.nio.file.Files.copy(new File(folder, photos.get(i)).toPath(), zip);
                        zip.closeEntry();
                    }
                }
                message = "Tanda con OCR guardada. Copia el archivo .psocr al PC por USB.";
            } catch (Exception error) {
                message = "No se pudo guardar la tanda con OCR. Puedes volver a intentarlo.";
            } finally {
                reader.close();
            }
            String result = message;
            runOnUiThread(() -> render(result));
        }).start();
    }

    private static String orderedText(Text recognized) {
        ArrayList<Text.Line> lines = new ArrayList<>();
        for (Text.TextBlock block : recognized.getTextBlocks()) {
            for (Text.Line line : block.getLines()) {
                if (line.getBoundingBox() != null) lines.add(line);
            }
        }
        if (lines.isEmpty()) return recognized.getText();
        int[] votes = new int[4];
        for (Text.Line line : lines) {
            Point[] corners = line.getCornerPoints();
            if (corners == null || corners.length < 2) continue;
            double angle = Math.atan2(corners[1].y - corners[0].y, corners[1].x - corners[0].x);
            int turn = Math.floorMod((int) Math.round(angle / (Math.PI / 2)), 4);
            votes[turn] += line.getText().length();
        }
        int dominant = 0;
        for (int i = 1; i < votes.length; i++) {
            if (votes[i] > votes[dominant]) dominant = i;
        }
        final int turn = dominant;
        lines.sort(Comparator.comparingInt(line -> rowPosition(line.getBoundingBox(), turn)));

        StringBuilder text = new StringBuilder();
        ArrayList<Text.Line> row = new ArrayList<>();
        Rect anchor = lines.get(0).getBoundingBox();
        for (Text.Line line : lines) {
            Rect box = line.getBoundingBox();
            int tolerance = Math.max(1, Math.min(rowHeight(anchor, turn), rowHeight(box, turn)) / 2);
            if (rowPosition(box, turn) - rowPosition(anchor, turn) > tolerance) {
                appendRow(text, row, turn);
                row.clear();
                anchor = box;
            }
            row.add(line);
        }
        appendRow(text, row, turn);
        return text.toString();
    }

    private static int rowHeight(Rect box, int turn) {
        return turn % 2 == 0 ? box.height() : box.width();
    }

    private static int rowPosition(Rect box, int turn) {
        switch (turn) {
            case 1: return -box.centerX();
            case 2: return -box.centerY();
            case 3: return box.centerX();
            default: return box.centerY();
        }
    }

    private static void appendRow(StringBuilder text, ArrayList<Text.Line> row, int turn) {
        row.sort(Comparator.comparingInt(line -> rowPosition(line.getBoundingBox(), (turn + 3) % 4)));
        for (int i = 0; i < row.size(); i++) {
            if (i > 0) text.append(' ');
            text.append(row.get(i).getText());
        }
        text.append('\n');
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
