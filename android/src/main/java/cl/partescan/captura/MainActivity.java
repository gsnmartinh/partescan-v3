package cl.partescan.captura;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.ImageDecoder;
import android.graphics.Matrix;
import java.io.FileOutputStream;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
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
    private FluentStyle fluent;
    private final ArrayList<String> pages = new ArrayList<>();
    private final ArrayList<Integer> attachments = new ArrayList<>();
    private int completedParts;
    private String part;
    private String certificate;
    private String pending;
    private int editingIndex = -1;
    private String undoDelete;
    private static final int OPEN_BATCH = 6;
    private boolean busy;
    private static final int TANDA = 0, CAPTURA = 1, GUARDAR = 2;
    private int screen = TANDA;

    private static final int PART = 1, CERTIFICATE = 2, SAVE = 3, NEXT = 4, SAVE_OCR = 5;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        fluent = new FluentStyle(this);
        getWindow().setStatusBarColor(fluent.background);
        getWindow().setNavigationBarColor(fluent.background);
        getWindow().getDecorView().setSystemUiVisibility(fluent.dark ? 0 : android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | android.view.View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        folder = new File(getFilesDir(), "capturas");
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
        if (state != null) { editingIndex = state.getInt("editingIndex", -1); screen = state.getInt("screen", TANDA); }
        else {
            File saved = new File(folder, "tanda.json");
            if (saved.isFile()) try { restore(new JSONObject(new String(Files.readAllBytes(saved.toPath()), StandardCharsets.UTF_8))); }
            catch (Exception error) { /* Las fotos originales siguen disponibles. */ }
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
        state.putInt("editingIndex", editingIndex);
        state.putInt("screen", screen);
    }

    @Override protected void onPause() {
        super.onPause();
        if (!busy) persist();
    }

    private JSONObject snapshot() throws org.json.JSONException {
        return new JSONObject().put("pages", new JSONArray(pages)).put("attachments", new JSONArray(attachments))
                .put("part", part == null ? JSONObject.NULL : part)
                .put("certificate", certificate == null ? JSONObject.NULL : certificate)
                .put("editingIndex", editingIndex);
    }

    private void restore(JSONObject saved) throws org.json.JSONException {
        pages.clear(); attachments.clear();
        JSONArray photos = saved.getJSONArray("pages"), certs = saved.getJSONArray("attachments");
        for (int i=0; i<photos.length(); i++) pages.add(photos.getString(i));
        for (int i=0; i<certs.length(); i++) attachments.add(certs.getInt(i));
        part = saved.isNull("part") ? null : saved.getString("part");
        certificate = saved.isNull("certificate") ? null : saved.getString("certificate");
        editingIndex = saved.optInt("editingIndex", -1);
        completedParts = pages.size() - attachments.size();
    }

    private void persist() {
        try {
            File temporary = new File(folder, "tanda.tmp");
            Files.write(temporary.toPath(), snapshot().toString().getBytes(StandardCharsets.UTF_8));
            Files.move(temporary.toPath(), new File(folder, "tanda.json").toPath(), StandardCopyOption.REPLACE_EXISTING);
        } catch (Exception error) { android.widget.Toast.makeText(this, "No se pudo guardar la tanda local. Guarda un archivo antes de cerrar.", android.widget.Toast.LENGTH_LONG).show(); }
    }

    private ArrayList<ArrayList<String>> groups() {
        ArrayList<ArrayList<String>> result = new ArrayList<>();
        for (int i=0; i<pages.size(); i++) {
            if (attachments.contains(i) && !result.isEmpty()) result.get(result.size()-1).add(pages.get(i));
            else { ArrayList<String> group = new ArrayList<>(); group.add(pages.get(i)); result.add(group); }
        }
        return result;
    }

    private void setGroups(ArrayList<ArrayList<String>> groups) {
        pages.clear(); attachments.clear();
        for (ArrayList<String> group : groups) {
            pages.add(group.get(0));
            if (group.size()>1) { attachments.add(pages.size()); pages.add(group.get(1)); }
        }
        completedParts = groups.size();
    }

    private void commitCurrent() {
        if (part == null) return;
        ArrayList<ArrayList<String>> all = groups();
        ArrayList<String> group = new ArrayList<>(); group.add(part);
        if (certificate != null) group.add(certificate);
        all.add(editingIndex < 0 ? all.size() : Math.min(editingIndex, all.size()), group);
        setGroups(all); part = certificate = null; editingIndex = -1;
    }

    private void editPart(int index) {
        commitCurrent();
        ArrayList<ArrayList<String>> all = groups();
        if (index < 0 || index >= all.size()) return;
        ArrayList<String> selected = all.remove(index);
        setGroups(all); part = selected.get(0); certificate = selected.size() > 1 ? selected.get(1) : null;
        editingIndex = index; screen = CAPTURA; render("");
    }

    private void removeCurrent() {
        new android.app.AlertDialog.Builder(this).setMessage("¿Eliminar este parte y su certificado de la tanda?")
            .setNegativeButton("Cancelar", null).setPositiveButton("Eliminar", (dialog, which) -> {
                try { undoDelete = snapshot().toString(); } catch (Exception error) { return; }
                part = certificate = null; editingIndex = -1;
                screen = TANDA;
                render("Parte eliminado de la tanda.");
            }).show();
    }

    private void openBatch() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.setType("*/*"); intent.addCategory(Intent.CATEGORY_OPENABLE);
        startActivityForResult(intent, OPEN_BATCH);
    }

    private static byte[] readLimited(java.io.InputStream input, int max) throws IOException {
        java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream();
        byte[] buffer = new byte[65536]; int count;
        while ((count = input.read(buffer)) != -1) {
            if (output.size() + count > max) throw new IOException("Archivo demasiado grande");
            output.write(buffer, 0, count);
        }
        return output.toByteArray();
    }

    private void importBatch(android.net.Uri uri) {
        progress("Abriendo la tanda…");
        new Thread(() -> {
            File archive = new File(folder, UUID.randomUUID() + ".psocr");
            ArrayList<String> imported = new ArrayList<>(); ArrayList<Integer> certs = new ArrayList<>();
            String error = null;
            try {
                try (java.io.InputStream input = getContentResolver().openInputStream(uri)) {
                    if (input == null) throw new IOException();
                    Files.copy(input, archive.toPath());
                }
                try (java.util.zip.ZipFile zip = new java.util.zip.ZipFile(archive)) {
                    JSONArray manifest;
                    try (java.io.InputStream input = zip.getInputStream(zip.getEntry("ocr.json"))) {
                        manifest = new JSONArray(new String(readLimited(input, 2000000), StandardCharsets.UTF_8));
                    }
                    if (manifest.length()<1 || manifest.length()>500) throw new IOException();
                    boolean previousCertificate = true;
                    for (int i=0; i<manifest.length(); i++) {
                        JSONObject item = manifest.getJSONObject(i);
                        String text = item.getString("texto");
                        boolean cert = item.getBoolean("certificado") || (text.toUpperCase(java.util.Locale.ROOT).contains("EXTRACTO DE INSCRIPCION") && text.contains("DATOS DEL"));
                        if (cert && previousCertificate) throw new IOException();
                        previousCertificate = cert;
                        String name = UUID.randomUUID()+".jpg";
                        try (java.io.InputStream input = zip.getInputStream(zip.getEntry(i+".jpg"))) {
                            byte[] photo = readLimited(input, 25000000);
                            android.graphics.BitmapFactory.Options bounds = new android.graphics.BitmapFactory.Options();
                            bounds.inJustDecodeBounds = true;
                            android.graphics.BitmapFactory.decodeByteArray(photo, 0, photo.length, bounds);
                            if (bounds.outWidth<1 || bounds.outHeight<1 || (long)bounds.outWidth*bounds.outHeight>40000000L) throw new IOException();
                            Files.write(new File(folder, name).toPath(), photo);
                        }
                        imported.add(name); if (cert) certs.add(i);
                    }
                }
            } catch (Exception failure) { error = "No se pudo abrir la tanda. Selecciona un archivo .psocr válido."; }
            finally { archive.delete(); }
            String message = error;
            runOnUiThread(() -> {
                if (message == null) {
                    pages.clear(); pages.addAll(imported); attachments.clear(); attachments.addAll(certs);
                    part = certificate = null; editingIndex = -1; undoDelete = null;
                    completedParts = pages.size()-attachments.size();
                } else { for (String name : imported) delete(name); }
                if (message == null) screen = TANDA;
                render(message == null ? "Tanda abierta. Toca un parte para revisarlo." : message);
            });
        }).start();
    }

    private int partCount() { return completedParts + (part == null ? 0 : 1); }

    private void navigate(int destination) {
        if (busy) return;
        if (destination != CAPTURA) commitCurrent();
        screen = destination;
        render("");
    }

    private void render(String message) {
        busy = false;
        if (screen != CAPTURA) commitCurrent();
        persist();
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(fluent.background);
        root.setFitsSystemWindows(true);
        setContentView(root);
        renderHeader(root);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(fluent.dp(20), fluent.dp(20), fluent.dp(20), fluent.dp(20));
        scroll.addView(body);
        if (!message.isEmpty() || undoDelete != null) renderNotice(body, message);
        if (screen == TANDA) renderBatch(body);
        else if (screen == CAPTURA) renderCapture(body);
        else renderSave(body);
        renderPrimaryAction(root);
        renderNavigation(root);
    }

    private void renderHeader(LinearLayout root) {
        LinearLayout header = row();
        header.setGravity(android.view.Gravity.CENTER_VERTICAL);
        header.setPadding(fluent.dp(20), fluent.dp(8), fluent.dp(8), fluent.dp(8));
        header.setBackgroundColor(fluent.surface);
        ImageView mark = new ImageView(this);
        mark.setImageDrawable(fluent.icon(R.drawable.ic_scan, fluent.brand));
        header.addView(mark, new LinearLayout.LayoutParams(fluent.dp(24), fluent.dp(24)));
        TextView title = new TextView(this);
        title.setText("ParteScan"); fluent.text(title, 20);
        LinearLayout.LayoutParams name = new LinearLayout.LayoutParams(0, -2, 1);
        name.leftMargin = fluent.dp(10); header.addView(title, name);
        iconAction(header, R.drawable.ic_more, "Opciones de la tanda", view -> {
            android.widget.PopupMenu menu = new android.widget.PopupMenu(this, view);
            menu.getMenu().add("Abrir tanda guardada").setOnMenuItemClickListener(item -> { requestOpen(); return true; });
            if (partCount() > 0) menu.getMenu().add("Nueva tanda").setOnMenuItemClickListener(item -> { requestNewBatch(); return true; });
            menu.show();
        });
        root.addView(header, new LinearLayout.LayoutParams(-1, -2));
        divider(root);
    }

    private void renderBatch(LinearLayout body) {
        heading(body, "Mi tanda", "Revisa tus capturas antes de llevarlas al computador.");
        int count = partCount();
        if (count == 0) {
            LinearLayout empty = fluent.card(body);
            empty.setGravity(android.view.Gravity.CENTER_HORIZONTAL);
            empty.setPadding(fluent.dp(24), fluent.dp(36), fluent.dp(24), fluent.dp(28));
            ImageView image = new ImageView(this);
            image.setImageDrawable(fluent.icon(R.drawable.ic_tanda, fluent.brand));
            empty.addView(image, new LinearLayout.LayoutParams(fluent.dp(48), fluent.dp(48)));
            space(empty, 20);
            label(empty, "Tu tanda empieza aquí", 20);
            TextView help = text(empty, "Escanea un parte y agrega su certificado si corresponde.", 16);
            help.setGravity(android.view.Gravity.CENTER);
            space(empty, 20);
            button(empty, "Abrir una tanda guardada", true, () -> requestOpen());
            text(body, "Las capturas se conservan en este teléfono mientras trabajas.", 14);
            return;
        }
        ArrayList<ArrayList<String>> all = groups();
        LinearLayout summary = fluent.card(body);
        label(summary, count + (count == 1 ? " parte en la tanda" : " partes en la tanda"), 20);
        text(summary, attachments.size() + (attachments.size() == 1 ? " certificado adjunto" : " certificados adjuntos")
                + " · " + pages.size() + " páginas", 14);
        space(body, 20);
        label(body, "Partes capturados", 16);
        for (int index = 0; index < all.size(); index++) {
            final int selected = index;
            ArrayList<String> group = all.get(index);
            LinearLayout card = fluent.card(body);
            card.setPadding(fluent.dp(12), fluent.dp(12), fluent.dp(4), fluent.dp(12));
            card.setOrientation(LinearLayout.HORIZONTAL);
            card.setGravity(android.view.Gravity.CENTER_VERTICAL);
            LinearLayout target = row();
            target.setGravity(android.view.Gravity.CENTER_VERTICAL);
            fluent.interactive(target, false);
            target.setContentDescription("Revisar parte " + (index + 1) + (group.size() > 1 ? ", con certificado" : ", sin certificado"));
            target.setOnClickListener(view -> editPart(selected));
            target.addView(thumbnail(group.get(0), 56, 72));
            LinearLayout detail = column();
            detail.setPadding(fluent.dp(12), fluent.dp(4), fluent.dp(4), fluent.dp(4));
            label(detail, "Parte " + (index + 1), 18);
            text(detail, group.size() > 1 ? "Certificado adjunto" : "Sin certificado", 14);
            target.addView(detail, new LinearLayout.LayoutParams(0, -2, 1));
            card.addView(target, new LinearLayout.LayoutParams(0, -2, 1));
            iconAction(card, R.drawable.ic_more, "Opciones del parte " + (index + 1), view -> {
                android.widget.PopupMenu menu = new android.widget.PopupMenu(this, view);
                menu.getMenu().add("Revisar parte").setOnMenuItemClickListener(item -> { editPart(selected); return true; });
                menu.getMenu().add("Eliminar parte").setOnMenuItemClickListener(item -> { removeListedPart(selected); return true; });
                menu.show();
            });
        }
    }

    private void renderCapture(LinearLayout body) {
        boolean editing = editingIndex >= 0;
        int number = editing ? editingIndex + 1 : completedParts + 1;
        heading(body, "Parte " + number, editing ? "Revisa el parte y su certificado." : "Primero el parte. Después, su certificado si corresponde.");
        LinearLayout document = fluent.card(body);
        LinearLayout title = row();
        title.setGravity(android.view.Gravity.CENTER_VERTICAL);
        TextView step = new TextView(this); step.setText("1  ·  Parte"); fluent.text(step, 18);
        title.addView(step, new LinearLayout.LayoutParams(0, -2, 1));
        if (part != null) iconAction(title, R.drawable.ic_more, "Opciones de la foto del parte", view -> {
            android.widget.PopupMenu menu = new android.widget.PopupMenu(this, view);
            menu.getMenu().add("Girar foto").setOnMenuItemClickListener(item -> { orientPhoto(part, false); return true; });
            menu.getMenu().add("Eliminar parte").setOnMenuItemClickListener(item -> { removeCurrent(); return true; });
            menu.show();
        });
        document.addView(title);
        if (part == null) {
            LinearLayout placeholder = column();
            placeholder.setGravity(android.view.Gravity.CENTER);
            placeholder.setPadding(fluent.dp(20), fluent.dp(40), fluent.dp(20), fluent.dp(40));
            placeholder.setBackground(fluent.surface());
            ImageView scan = new ImageView(this); scan.setImageDrawable(fluent.icon(R.drawable.ic_scan, fluent.brand));
            placeholder.addView(scan, new LinearLayout.LayoutParams(fluent.dp(48), fluent.dp(48)));
            space(placeholder, 20);
            TextView hint = text(placeholder, "Encuadra el documento completo", 16);
            hint.setGravity(android.view.Gravity.CENTER);
            document.addView(placeholder);
            space(document, 12);
            text(document, "Usa buena luz y apoya el documento en una superficie plana.", 14);
            return;
        }
        preview(document, part, "Foto del parte");
        text(document, "Toca la imagen para ampliarla.", 12);
        button(document, "Repetir foto", true, () -> capture(PART));
        LinearLayout attachment = fluent.card(body);
        LinearLayout certificateTitle = row();
        certificateTitle.setGravity(android.view.Gravity.CENTER_VERTICAL);
        LinearLayout words = column();
        label(words, "2  ·  Certificado", 18);
        text(words, "Opcional · Pertenece a este parte", 12);
        certificateTitle.addView(words, new LinearLayout.LayoutParams(0, -2, 1));
        if (certificate != null) iconAction(certificateTitle, R.drawable.ic_more, "Opciones del certificado", view -> {
            android.widget.PopupMenu menu = new android.widget.PopupMenu(this, view);
            menu.getMenu().add("Girar foto").setOnMenuItemClickListener(item -> { orientPhoto(certificate, false); return true; });
            menu.getMenu().add("Quitar certificado").setOnMenuItemClickListener(item -> {
                new android.app.AlertDialog.Builder(this).setTitle("¿Quitar el certificado?")
                    .setMessage("Se conserva la foto del parte.").setNegativeButton("Cancelar", null)
                    .setPositiveButton("Quitar", (dialog, which) -> { undoDelete = null; delete(certificate); certificate = null; render(""); }).show();
                return true;
            });
            menu.show();
        });
        attachment.addView(certificateTitle);
        if (certificate == null) button(attachment, "Agregar certificado", true, () -> capture(CERTIFICATE));
        else {
            LinearLayout certificateRow = row(); certificateRow.setGravity(android.view.Gravity.CENTER_VERTICAL);
            ImageView photo = thumbnail(certificate, 64, 80);
            photo.setContentDescription("Ampliar certificado");
            photo.setOnClickListener(view -> showPhoto(certificate, "Certificado"));
            certificateRow.addView(photo);
            LinearLayout actions = column(); actions.setPadding(fluent.dp(12), 0, 0, 0);
            text(actions, "Certificado adjunto", 16);
            button(actions, "Repetir foto", true, () -> capture(CERTIFICATE));
            certificateRow.addView(actions, new LinearLayout.LayoutParams(0, -2, 1));
            attachment.addView(certificateRow);
        }
    }

    private void renderSave(LinearLayout body) {
        heading(body, "Guardar tanda", "Elige cómo quieres llevar tus documentos al computador.");
        int count = partCount();
        LinearLayout summary = fluent.card(body);
        label(summary, count + (count == 1 ? " parte listo para guardar" : " partes listos para guardar"), 20);
        text(summary, attachments.size() + " certificados · " + pages.size() + " páginas", 14);
        LinearLayout recommended = fluent.card(body);
        text(recommended, "RECOMENDADO", 12).setTextColor(fluent.brand);
        label(recommended, "Archivo para ParteScan", 20);
        text(recommended, "Conserva las imágenes y el texto reconocido. Puedes revisarlo o continuar trabajando en ParteScan.", 16);
        text(recommended, "Formato .psocr · Se prepara en este teléfono", 14);
        LinearLayout other = fluent.card(body);
        label(other, "Copia en PDF", 18);
        text(other, "Para consultar o imprimir las imágenes de los documentos.", 14);
        button(other, "Guardar como PDF", count > 0, () -> save(false));
        space(body, 12);
        text(body, count == 0 ? "Agrega un parte en Escanear para preparar tu archivo." : "Después de guardar, copia el archivo al computador por USB y ábrelo en ParteScan.", 14);
    }

    private void renderPrimaryAction(LinearLayout root) {
        LinearLayout actions = column();
        actions.setBackgroundColor(fluent.surface);
        actions.setPadding(fluent.dp(20), fluent.dp(8), fluent.dp(20), fluent.dp(8));
        if (screen == TANDA) {
            button(actions, partCount() == 0 ? "Escanear primer parte" : "Agregar parte", true, () -> {
                screen = CAPTURA; render(""); capture(PART);
            }, true);
        } else if (screen == CAPTURA && part == null) {
            button(actions, "Escanear parte", true, () -> capture(PART), true);
        } else if (screen == CAPTURA) {
            button(actions, editingIndex >= 0 ? "Guardar cambios" : "Añadir a la tanda", true, () -> {
                boolean editing = editingIndex >= 0; commitCurrent(); screen = TANDA;
                render(editing ? "Cambios guardados." : "Parte añadido a la tanda.");
            }, true);
            button(actions, "Guardar y escanear otro", true, () -> capture(NEXT));
        } else button(actions, "Guardar para ParteScan", partCount() > 0, () -> save(true), true);
        divider(root);
        root.addView(actions, new LinearLayout.LayoutParams(-1, -2));
    }

    private void renderNavigation(LinearLayout root) {
        LinearLayout navigation = row();
        navigation.setPadding(fluent.dp(8), fluent.dp(4), fluent.dp(8), fluent.dp(6));
        navigation.setBackgroundColor(fluent.surface);
        String[] names = {"Tanda", "Escanear", "Guardar"};
        int[] icons = {R.drawable.ic_tanda, R.drawable.ic_scan, R.drawable.ic_save};
        for (int tab = 0; tab < names.length; tab++) {
            final int destination = tab;
            LinearLayout item = column(); item.setGravity(android.view.Gravity.CENTER);
            item.setPadding(fluent.dp(8), fluent.dp(8), fluent.dp(8), fluent.dp(6));
            fluent.interactive(item, tab == screen);
            item.setSelected(tab == screen); item.setContentDescription(names[tab]);
            item.setImportantForAccessibility(android.view.View.IMPORTANT_FOR_ACCESSIBILITY_YES);
            ImageView icon = new ImageView(this);
            icon.setImageDrawable(fluent.icon(icons[tab], tab == screen ? fluent.brand : fluent.secondary));
            item.addView(icon, new LinearLayout.LayoutParams(fluent.dp(24), fluent.dp(24)));
            TextView caption = text(item, names[tab], 12);
            caption.setTextColor(tab == screen ? fluent.brand : fluent.secondary);
            caption.setGravity(android.view.Gravity.CENTER);
            item.setOnClickListener(view -> navigate(destination));
            navigation.addView(item, new LinearLayout.LayoutParams(0, -2, 1));
        }
        root.addView(navigation, new LinearLayout.LayoutParams(-1, -2));
    }

    private void requestOpen() {
        if (partCount() == 0) { openBatch(); return; }
        new android.app.AlertDialog.Builder(this).setTitle("¿Abrir otra tanda?")
            .setMessage("Se reemplazará la tanda actual. Guarda un archivo si quieres conservarla.")
            .setNegativeButton("Cancelar", null).setPositiveButton("Abrir archivo", (dialog, which) -> openBatch()).show();
    }

    private void requestNewBatch() {
        new android.app.AlertDialog.Builder(this).setTitle("¿Empezar una tanda nueva?")
            .setMessage("Se borrarán las capturas de esta tanda del teléfono. Guarda un archivo si quieres conservarlas.")
            .setNegativeButton("Cancelar", null).setPositiveButton("Nueva tanda", (dialog, which) -> {
                pages.clear(); attachments.clear(); completedParts = 0;
                part = certificate = null; editingIndex = -1; undoDelete = null;
                File[] oldPhotos = folder.listFiles((dir, name) -> name.endsWith(".jpg"));
                if (oldPhotos != null) for (File photo : oldPhotos) photo.delete();
                screen = TANDA; render("");
            }).show();
    }

    private void removeListedPart(int index) {
        new android.app.AlertDialog.Builder(this).setTitle("¿Eliminar el parte " + (index + 1) + "?")
            .setMessage("Se quitará de la tanda junto con su certificado. Puedes deshacer el cambio.")
            .setNegativeButton("Cancelar", null).setPositiveButton("Eliminar", (dialog, which) -> {
                try { undoDelete = snapshot().toString(); } catch (Exception error) { return; }
                ArrayList<ArrayList<String>> all = groups(); all.remove(index); setGroups(all);
                render("Parte eliminado de la tanda.");
            }).show();
    }

    private void renderNotice(LinearLayout body, String message) {
        LinearLayout notice = column();
        notice.setPadding(fluent.dp(12), fluent.dp(12), fluent.dp(12), fluent.dp(8));
        notice.setBackground(fluent.selected());
        notice.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);
        text(notice, message.isEmpty() ? "Puedes recuperar el parte eliminado." : message, 14).setTextColor(fluent.foreground);
        if (undoDelete != null) button(notice, "Deshacer eliminación", true, () -> {
            try { restore(new JSONObject(undoDelete)); undoDelete = null; commitCurrent(); screen = TANDA; render("Parte recuperado."); }
            catch (Exception error) { render("No se pudo recuperar el parte."); }
        });
        body.addView(notice); space(body, 16);
    }

    private LinearLayout column() { LinearLayout view = new LinearLayout(this); view.setOrientation(LinearLayout.VERTICAL); return view; }
    private LinearLayout row() { LinearLayout view = new LinearLayout(this); view.setOrientation(LinearLayout.HORIZONTAL); return view; }
    private void heading(LinearLayout body, String title, String subtitle) { label(body, title, 28); text(body, subtitle, 14); }
    private TextView text(LinearLayout body, String value, int size) {
        TextView view = new TextView(this); view.setText(value); fluent.text(view, size);
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, -2); layout.bottomMargin = fluent.dp(8);
        body.addView(view, layout); return view;
    }
    private void space(LinearLayout body, int height) { body.addView(new android.view.View(this), new LinearLayout.LayoutParams(1, fluent.dp(height))); }
    private void divider(LinearLayout root) { android.view.View line = new android.view.View(this); line.setBackgroundColor(fluent.dark ? 0xFF424242 : 0xFFE0E0E0); root.addView(line, new LinearLayout.LayoutParams(-1, fluent.dp(1))); }
    private void iconAction(LinearLayout body, int resource, String description, android.view.View.OnClickListener action) {
        android.widget.ImageButton button = new android.widget.ImageButton(this);
        button.setImageDrawable(fluent.icon(resource, fluent.secondary)); button.setContentDescription(description);
        button.setPadding(fluent.dp(12), fluent.dp(12), fluent.dp(12), fluent.dp(12));
        fluent.interactive(button, false); button.setOnClickListener(action);
        body.addView(button, new LinearLayout.LayoutParams(fluent.dp(48), fluent.dp(48)));
    }
    private ImageView thumbnail(String name, int width, int height) {
        ImageView photo = new ImageView(this); photo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        photo.setBackground(fluent.surface()); photo.setClipToOutline(true);
        photo.setLayoutParams(new LinearLayout.LayoutParams(fluent.dp(width), fluent.dp(height)));
        try { photo.setImageBitmap(decode(name, fluent.dp(height * 2))); }
        catch (IOException error) { photo.setImageDrawable(fluent.icon(R.drawable.ic_document, fluent.secondary)); }
        return photo;
    }
    private void showPhoto(String name, String description) {
        try {
            ImageView full = new ImageView(this); full.setImageBitmap(decode(name, 2400)); full.setAdjustViewBounds(true);
            ScrollView document = new ScrollView(this); document.addView(full);
            new android.app.AlertDialog.Builder(this).setTitle(description).setView(document).setPositiveButton("Cerrar", null).show();
        } catch (IOException error) { render("No se pudo abrir la imagen."); }
    }

    private void label(LinearLayout body, String text, int size) {
        TextView view = new TextView(this);
        view.setText(text);
        fluent.text(view, size);
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, -2);
        layout.bottomMargin = fluent.dp(8);
        body.addView(view, layout);
    }

    private void button(LinearLayout body, String text, boolean enabled, Runnable action) {
        button(body, text, enabled, action, false);
    }

    private void button(LinearLayout body, String text, boolean enabled, Runnable action, boolean primary) {
        Button button = new Button(this);
        button.setText(text);
        button.setEnabled(enabled);
        fluent.button(button, primary, enabled);
        button.setOnClickListener(view -> action.run());
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, -2);
        layout.topMargin = fluent.dp(4);
        layout.bottomMargin = fluent.dp(4);
        body.addView(button, layout);
    }

    private void progress(String message) {
        busy = true;
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setGravity(android.view.Gravity.CENTER);
        panel.setPadding(fluent.dp(24), fluent.dp(24), fluent.dp(24), fluent.dp(24));
        panel.setBackgroundColor(fluent.background);
        android.widget.ProgressBar spinner = new android.widget.ProgressBar(this);
        spinner.setIndeterminateTintList(android.content.res.ColorStateList.valueOf(fluent.brand));
        panel.addView(spinner);
        TextView text = new TextView(this);
        text.setGravity(android.view.Gravity.CENTER);
        text.setText(message);
        fluent.text(text, 16);
        text.setPadding(0, fluent.dp(16), 0, 0);
        text.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);
        panel.addView(text);
        setContentView(panel);
    }

    private void preview(LinearLayout body, String name, String description) {
        if (name == null) return;
        try {
            ImageView view = new ImageView(this);
            view.setContentDescription(description);
            view.setScaleType(ImageView.ScaleType.FIT_CENTER);
            view.setBackground(fluent.surface());
            view.setClipToOutline(true);
            view.setImageBitmap(decode(name, 500));
            view.setOnClickListener(v -> {
                try {
                    ImageView full = new ImageView(this);
                    full.setImageBitmap(decode(name, 2400)); full.setAdjustViewBounds(true);
                    ScrollView document = new ScrollView(this); document.addView(full);
                    new android.app.AlertDialog.Builder(this).setTitle(description).setView(document).setPositiveButton("Cerrar", null).show();
                } catch (IOException error) { render("No se pudo abrir la imagen."); }
            });
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
        screen = CAPTURA;
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
        if (request == OPEN_BATCH && result == RESULT_OK && data != null && data.getData() != null) {
            importBatch(data.getData()); return;
        }
        if (request == PART || request == CERTIFICATE || request == NEXT) {
            String captured = pending;
            pending = null;
            if (captured == null) return;
            if (result != RESULT_OK || new File(folder, captured).length() == 0) {
                delete(captured);
                render("No se guardó una foto nueva.");
                return;
            }
            undoDelete = null;
            if (request == NEXT) {
                commitCurrent();
                part = captured;
                certificate = null;
            } else if (request == PART) {
                delete(part);
                part = captured;
            } else {
                delete(certificate);
                certificate = captured;
            }
            orientPhoto(captured, true);
        } else if (request == SAVE_OCR && result == RESULT_OK && data != null && data.getData() != null) {
            exportOcr(data.getData());
        } else if (request == SAVE && result == RESULT_OK && data != null && data.getData() != null) {
            PdfDocument pdf = new PdfDocument();
            try {
                int pageNumber = 1;
                commitCurrent();
                for (String page : pages) addPage(pdf, page, pageNumber++);
                try (OutputStream output = getContentResolver().openOutputStream(data.getData())) {
                    if (output == null) throw new IOException();
                    pdf.writeTo(output);
                }
                screen = GUARDAR;
                render("PDF guardado. Ya puedes copiarlo al computador.");
            } catch (IOException | RuntimeException error) {
                render("No se pudo guardar el PDF. Puedes intentarlo nuevamente.");
            } finally {
                pdf.close();
            }
        }
    }

    // ImageDecoder already applies camera EXIF. Detect text direction in those decoded pixels.
    private void orientPhoto(String name, boolean automatic) {
        undoDelete = null;
        progress(automatic ? "Orientando la foto…" : "Girando la foto…");
        setRequestedOrientation(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_LOCKED);
        new Thread(() -> {
            String message = "";
            Bitmap bitmap = null;
            TextRecognizer reader = null;
            try {
                int degrees = 90;
                if (automatic) {
                    reader = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
                    Bitmap sample = decode(name, 2000);
                    try {
                        Text text = Tasks.await(reader.process(InputImage.fromBitmap(sample, 0)));
                        int[] votes = orientationVotes(text);
                        int turn = dominantTurn(votes);
                        int total = votes[0] + votes[1] + votes[2] + votes[3];
                        // Avoid rotating sparse or mixed-direction text on weak evidence.
                        degrees = total >= 20 && votes[turn] * 100L >= total * 65L
                                ? (360 - turn * 90) % 360 : 0;
                        if (total < 20 || votes[turn] * 100L < total * 65L)
                            message = "No se pudo determinar la orientación. Revisa la foto y usa Girar si hace falta.";
                    } finally {
                        sample.recycle();
                    }
                }
                if (degrees != 0) {
                    bitmap = decode(name, 4000);
                    Matrix matrix = new Matrix();
                    matrix.postRotate(degrees);
                    Bitmap rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.getWidth(), bitmap.getHeight(), matrix, true);
                    try {
                        File temporary = new File(folder, name + ".rotating");
                        try {
                            try (FileOutputStream output = new FileOutputStream(temporary)) {
                                if (!rotated.compress(Bitmap.CompressFormat.JPEG, 95, output)) throw new IOException();
                            }
                            Files.move(temporary.toPath(), new File(folder, name).toPath(), StandardCopyOption.REPLACE_EXISTING);
                        } finally {
                            temporary.delete();
                        }
                    } finally {
                        if (rotated != bitmap) rotated.recycle();
                    }
                }
            } catch (Exception error) {
                message = "No se pudo girar la foto. Se conserva la captura; puedes usar Girar o repetirla.";
            } finally {
                if (bitmap != null) bitmap.recycle();
                if (reader != null) reader.close();
            }
            String result = message;
            runOnUiThread(() -> {
                render(result);
                setRequestedOrientation(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
            });
        }).start();
    }

    @Override public void onBackPressed() {
        if (busy) return;
        if (screen != TANDA) { navigate(TANDA); return; }
        super.onBackPressed();
    }

    private static int[] orientationVotes(Text recognized) {
        int[] votes = new int[4];
        for (Text.TextBlock block : recognized.getTextBlocks()) {
            for (Text.Line line : block.getLines()) {
                Point[] corners = line.getCornerPoints();
                if (corners == null || corners.length < 2) continue;
                int dx = corners[1].x - corners[0].x;
                int dy = corners[1].y - corners[0].y;
                if (dx == 0 && dy == 0) continue;
                double angle = Math.atan2(dy, dx);
                int turn = Math.floorMod((int) Math.round(angle / (Math.PI / 2)), 4);
                votes[turn] += line.getText().length();
            }
        }
        return votes;
    }

    private static int dominantTurn(int[] votes) {
        int dominant = 0;
        for (int i = 1; i < votes.length; i++) {
            if (votes[i] > votes[dominant]) dominant = i;
        }
        return dominant;
    }

    private void exportOcr(android.net.Uri destination) {
        commitCurrent();
        ArrayList<String> photos = new ArrayList<>(pages);
        ArrayList<Integer> certificates = new ArrayList<>(attachments);
        if (part != null) photos.add(part);
        if (certificate != null) {
            certificates.add(photos.size());
            photos.add(certificate);
        }
        progress("Reconociendo texto en el teléfono…");
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
                message = "Tanda guardada. Lleva el archivo .psocr al computador y ábrelo en ParteScan.";
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
        final int turn = dominantTurn(orientationVotes(recognized));
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
