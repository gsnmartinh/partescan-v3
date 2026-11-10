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
import android.view.View;
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
    private final java.util.concurrent.ExecutorService ocrQueue =
            java.util.concurrent.Executors.newSingleThreadExecutor();
    private final java.util.Set<File> queuedOcr = new java.util.HashSet<>();
    private final java.util.Map<TextView, java.util.List<String>> photoNotices = new java.util.HashMap<>();
    private TextView ocrStatus;
    private int completedParts;
    private String part;
    private String certificate;
    private String pending;
    private int editingIndex = -1;
    private String undoDelete;
    private static final int OPEN_BATCH = 6;
    private static final int SAVE_BLOCKS = 7;
    private static final int PARTS_PER_BLOCK = 25;
    private boolean busy;
    private android.window.OnBackInvokedCallback systemBackCallback;
    private static final int TANDA = 0, CAPTURA = 1, GUARDAR = 2;
    private int screen = TANDA;

    private static final int PART = 1, CERTIFICATE = 2, SAVE = 3, NEXT = 4, SAVE_OCR = 5;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            systemBackCallback = this::onBackPressed;
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, systemBackCallback);
        }
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
        new AppUpdater(this).check();
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

    @Override protected void onDestroy() {
        ocrQueue.shutdown();
        if (android.os.Build.VERSION.SDK_INT >= 33 && systemBackCallback != null) {
            getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(systemBackCallback);
        }
        super.onDestroy();
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
        photoNotices.clear();
        if (screen != CAPTURA) commitCurrent();
        persist();
        for (String page : pages) queueOcr(page);
        queueOcr(part);
        queueOcr(certificate);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(fluent.background);
        root.setFitsSystemWindows(true);
        setContentView(root);
        renderHeader(root);
        ocrStatus = text(root, "", 14);
        ocrStatus.setPadding(fluent.dp(20), fluent.dp(6), fluent.dp(20), fluent.dp(6));
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
        updateOcrStatus();
    }

    private void renderHeader(LinearLayout root) {
        LinearLayout header = row();
        header.setGravity(android.view.Gravity.CENTER_VERTICAL);
        header.setPadding(fluent.dp(20), fluent.dp(8), fluent.dp(8), fluent.dp(8));
        header.setBackgroundColor(fluent.surface);
        ImageView mark = new ImageView(this);
        mark.setImageDrawable(getDrawable(R.drawable.brand_capture));
        header.addView(mark, new LinearLayout.LayoutParams(fluent.dp(32), fluent.dp(32)));
        TextView title = new TextView(this);
        title.setText("ParteScan"); fluent.text(title, 20);
        LinearLayout.LayoutParams name = new LinearLayout.LayoutParams(0, -2, 1);
        name.leftMargin = fluent.dp(10); header.addView(title, name);
        iconAction(header, R.drawable.ic_more, "Opciones de la tanda", view -> {
            android.widget.PopupMenu menu = new android.widget.PopupMenu(this, view);
            menu.getMenu().add("Abrir tanda guardada").setOnMenuItemClickListener(item -> { requestOpen(); return true; });
            if (partCount() > 0) menu.getMenu().add("Nueva tanda").setOnMenuItemClickListener(item -> { requestNewBatch(); return true; });
            if (partCount() > 0) menu.getMenu().add("Exportar copia en PDF").setOnMenuItemClickListener(item -> { save(false); return true; });
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
            photoNotices.put(text(detail, "", 14), group);
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
        compactPhoto(document, part, "Foto del parte", PART);
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
        else compactPhoto(attachment, certificate, "Certificado", CERTIFICATE);
    }

    private void renderSave(LinearLayout body) {
        heading(body, "Guardar tanda", "Prepara tu archivo para el computador.");
        int count = partCount();
        LinearLayout summary = fluent.card(body);
        label(summary, count + (count == 1 ? " parte listo para guardar" : " partes listos para guardar"), 20);
        text(summary, attachments.size() + (attachments.size() == 1 ? " certificado · " : " certificados · ") + pages.size() + " páginas", 14);
        LinearLayout recommended = fluent.card(body);
        text(recommended, "RECOMENDADO", 12).setTextColor(fluent.brand);
        label(recommended, "Archivo para ParteScan", 20);
        text(recommended, "Imágenes y texto en un solo archivo, para revisar y editar en ParteScan.", 16);
        text(recommended, "Formato .psocr · Se prepara en este teléfono", 14);
        if (count > PARTS_PER_BLOCK) {
            button(recommended, "Guardar por bloques de 25 partes", true, () -> {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                intent.putExtra(Intent.EXTRA_LOCAL_ONLY, true);
                try {
                    startActivityForResult(intent, SAVE_BLOCKS);
                } catch (RuntimeException error) {
                    render("No se pudo abrir el selector de carpetas.");
                }
            });
        }
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
            item.setAccessibilityDelegate(new android.view.View.AccessibilityDelegate() {
                @Override public void onInitializeAccessibilityNodeInfo(android.view.View view, android.view.accessibility.AccessibilityNodeInfo info) {
                    super.onInitializeAccessibilityNodeInfo(view, info);
                    info.setClassName(Button.class.getName());
                }
            });
            ImageView icon = new ImageView(this);
            icon.setImportantForAccessibility(android.view.View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            icon.setImageDrawable(fluent.icon(icons[tab], tab == screen ? fluent.brand : fluent.secondary));
            item.addView(icon, new LinearLayout.LayoutParams(fluent.dp(24), fluent.dp(24)));
            TextView caption = text(item, names[tab], 12);
            caption.setImportantForAccessibility(android.view.View.IMPORTANT_FOR_ACCESSIBILITY_NO);
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
            ZoomImageView full = new ZoomImageView(this);
            full.setImageBitmap(decode(name, 3200));
            full.setLayoutParams(new android.widget.FrameLayout.LayoutParams(-1,
                    fluent.dp(getResources().getConfiguration().screenHeightDp * 3 / 4)));
            new android.app.AlertDialog.Builder(this).setTitle(description).setView(full)
                    .setPositiveButton("Cerrar", null).show();
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

    private TextView progress(String message) {
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
        return text;
    }

    private void compactPhoto(LinearLayout body, String name, String description, int captureMode) {
        photoNotices.put(text(body, "", 14), java.util.Collections.singletonList(name));
        LinearLayout photoRow = row();
        photoRow.setGravity(android.view.Gravity.CENTER_VERTICAL);
        ImageView photo = thumbnail(name, 56, 72);
        photo.setContentDescription("Ampliar: " + description);
        photo.setOnClickListener(view -> showPhoto(name, description));
        photoRow.addView(photo);
        LinearLayout actions = column();
        actions.setPadding(fluent.dp(12), 0, 0, 0);
        text(actions, "Toca la foto para ampliarla.", 12);
        button(actions, "Repetir foto", true, () -> capture(captureMode));
        photoRow.addView(actions, new LinearLayout.LayoutParams(0, -2, 1));
        body.addView(photoRow);
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
        } catch (android.content.ActivityNotFoundException error) {
            cameraFailure(error, "No encontré una app de cámara. Comprueba que la cámara del teléfono esté disponible.");
        } catch (SecurityException error) {
            cameraFailure(error, "El teléfono no permitió abrir la cámara. Comprueba que la app Cámara funcione fuera de ParteScan y revisa el aviso de seguridad del teléfono.");
        } catch (IOException | IllegalArgumentException error) {
            cameraFailure(error, "No se pudo preparar el archivo de la foto. Vuelve a intentarlo.");
        } catch (RuntimeException error) {
            cameraFailure(error, "No se pudo abrir la cámara. Comprueba que la app Cámara funcione en el teléfono e inténtalo de nuevo.");
        }
    }

    private void cameraFailure(Exception error, String message) {
        android.util.Log.e("ParteScan", "No se pudo iniciar la captura de una foto", error);
        delete(pending);
        pending = null;
        render(message);
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
        } else if ((request == SAVE_OCR || request == SAVE_BLOCKS) && result == RESULT_OK && data != null && data.getData() != null) {
            exportOcr(data.getData(), request == SAVE_BLOCKS);
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
                            File previousOcr = ocrCache(name);
                            Files.move(temporary.toPath(), new File(folder, name).toPath(), StandardCopyOption.REPLACE_EXISTING);
                            new android.util.AtomicFile(previousOcr).delete();
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

    private File ocrCache(String name) {
        File photo = new File(folder, name);
        return new File(folder, name + "." + photo.lastModified() + "." + photo.length() + ".v2.ocr");
    }

    private void updateOcrStatus() {
        ArrayList<String> photos = new ArrayList<>(pages);
        if (part != null) photos.add(part);
        if (certificate != null) photos.add(certificate);
        int read = 0;
        for (String photo : photos) if (ocrCache(photo).isFile()) read++;
        if (ocrStatus != null) {
            ocrStatus.setVisibility(photos.isEmpty() ? View.GONE : View.VISIBLE);
            ocrStatus.setText(read + " de " + photos.size() + " páginas leídas");
        }
        photoNotices.forEach((notice, names) -> {
            boolean review = false;
            for (String name : names) {
                File cache = ocrCache(name);
                if (cache.isFile() && cache.length() < 80) review = true;
            }
            notice.setText(review ? "Revisar foto · poco texto legible" : "");
            notice.setVisibility(review ? View.VISIBLE : View.GONE);
        });
    }

    private void queueOcr(String name) {
        if (name == null || ocrQueue.isShutdown()) return;
        File cache = ocrCache(name);
        if (cache.isFile() || !queuedOcr.add(cache)) return;
        ocrQueue.execute(() -> {
            try {
                if (new File(folder, name).isFile() && cache.equals(ocrCache(name))) readOcr(name);
            } catch (Exception error) {
                // Al exportar se reintentan las páginas que quedaron pendientes.
            } finally {
                runOnUiThread(() -> {
                    queuedOcr.remove(cache);
                    if (!busy && !isDestroyed()) updateOcrStatus();
                });
            }
        });
    }

    private String readOcr(String name) throws Exception {
        File cache = ocrCache(name);
        if (cache.isFile()) {
            try {
                return new String(Files.readAllBytes(cache.toPath()), StandardCharsets.UTF_8);
            } catch (IOException error) {
                // Si la copia local no se puede leer, se vuelve a reconocer la foto.
            }
        }
        Bitmap bitmap = decode(name, 3000);
        TextRecognizer reader = null;
        String text;
        try {
            reader = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            text = orderedText(Tasks.await(reader.process(InputImage.fromBitmap(bitmap, 0))));
            text = rereadMissing(reader, bitmap, text);
        } finally {
            bitmap.recycle();
            if (reader != null) reader.close();
        }
        if (new File(folder, name).isFile() && cache.equals(ocrCache(name))) {
            android.util.AtomicFile target = new android.util.AtomicFile(cache);
            FileOutputStream output = null;
            try {
                output = target.startWrite();
                output.write(text.getBytes(StandardCharsets.UTF_8));
                target.finishWrite(output);
            } catch (IOException error) {
                target.failWrite(output);
            }
        }
        return text;
    }

    private String rereadMissing(TextRecognizer reader, Bitmap bitmap, String text) {
        String normalized = java.text.Normalizer.normalize(text, java.text.Normalizer.Form.NFD)
                .replaceAll("\\p{M}", "").toUpperCase(java.util.Locale.ROOT);
        String missing;
        int start = 0, end = 100;
        if (normalized.contains("ANTECEDENTES DEL INFRACTOR")
                && !normalized.matches("(?s).*(NOTIFICAD[OA]\\s+PERSONALMENTE|EMPADRONAD[OA]).*")) {
            start = 65;
            missing = "NOTIFICAD[OA]\\s+PERSONALMENTE|EMPADRONAD[OA]";
        } else if (normalized.contains("DATOS DEL PROPIETARIO")
                && !normalized.matches("(?s).*R\\.?\\s*U\\.?\\s*[NT]\\.?\\s*[:;]?\\s*[0-9. ]{7,14}[-–]\\s*[0-9K].*")) {
            start = 30;
            end = 85;
            missing = "R\\.?\\s*U\\.?\\s*[NT]\\.?\\s*[:;]?\\s*[0-9. ]{7,14}[-–]\\s*[0-9K]";
        } else if (normalized.contains("JUZGADO") && !normalized.matches("(?s).*BOLETA[^\\n]{0,25}\\d{4,}.*")) {
            end = 35;
            missing = "(?:BOLETA|PARTE)[^\\n]{0,25}\\d{4,}";
        } else if (normalized.contains("VEHICULO")
                && !normalized.matches("(?s).*(?:PATENTE|P\\.?P\\.?U\\.?)[^\\n]{0,12}[A-Z]{2,4}[- .]*\\d{2,4}.*")) {
            start = 35;
            end = 85;
            missing = "(?:PATENTE|P\\.?P\\.?U\\.?)[^\\w\\n]{0,12}[A-Z]{2,4}[- .]*\\d{2,4}";
        } else {
            return text;
        }
        int top = bitmap.getHeight() * start / 100;
        Bitmap crop = Bitmap.createBitmap(bitmap, 0, top, bitmap.getWidth(),
                Math.max(1, bitmap.getHeight() * end / 100 - top));
        try {
            String extra = orderedText(Tasks.await(reader.process(InputImage.fromBitmap(crop, 0))));
            java.util.regex.Matcher match = java.util.regex.Pattern.compile(missing, java.util.regex.Pattern.CASE_INSENSITIVE).matcher(extra);
            if (match.find()) {
                String line = match.group();
                int owner = normalized.indexOf("DATOS DEL PROPIETARIO");
                if (owner >= 0 && start == 30) {
                    java.util.regex.Matcher header = java.util.regex.Pattern.compile("(?im)^.*DATOS DEL PROPIETARIO[^\\r\\n]*").matcher(text);
                    if (header.find()) return text.substring(0, header.end()) + "\n" + line + text.substring(header.end());
                } else if (start == 65 || start == 35) return text + "\n" + line;
                else return line + "\n" + text;
            }
        } catch (Exception error) {
            // La primera lectura sigue disponible.
        } finally {
            if (crop != bitmap) crop.recycle();
        }
        return text;
    }

    private void exportOcr(android.net.Uri destination, boolean byBlocks) {
        commitCurrent();
        ArrayList<ArrayList<String>> parts = groups();
        TextView status = progress("Completando las lecturas pendientes…");
        ocrQueue.execute(() -> {
            int saved = 0;
            try {
                int size = byBlocks ? PARTS_PER_BLOCK : Math.max(1, parts.size());
                String stamp = new java.text.SimpleDateFormat("yyyyMMdd-HHmmss", java.util.Locale.ROOT)
                        .format(new java.util.Date());
                for (int offset = 0; offset < parts.size(); offset += size) {
                    android.net.Uri output = destination;
                    if (byBlocks) {
                        android.net.Uri parent = android.provider.DocumentsContract.buildDocumentUriUsingTree(
                                destination, android.provider.DocumentsContract.getTreeDocumentId(destination));
                        output = android.provider.DocumentsContract.createDocument(getContentResolver(), parent,
                                "application/octet-stream", String.format(java.util.Locale.ROOT,
                                        "ParteScan-%s-bloque-%03d.psocr", stamp, saved + 1));
                        if (output == null) throw new IOException("No se pudo crear el bloque");
                    }
                    try {
                        writeOcrBlock(parts.subList(offset, Math.min(offset + size, parts.size())), output, status);
                    } catch (Exception error) {
                        if (byBlocks) {
                            try { android.provider.DocumentsContract.deleteDocument(getContentResolver(), output); }
                            catch (Exception ignored) { }
                        }
                        throw error;
                    }
                    saved++;
                }
                String message = byBlocks ? saved + " bloques guardados y verificados."
                        : "Tanda guardada. Lleva el archivo .psocr al computador y ábrelo en ParteScan.";
                runOnUiThread(() -> { if (!isDestroyed()) render(message); });
            } catch (Exception error) {
                String message = (saved > 0 ? saved + " bloques verificados. " : "")
                        + "No se completó la exportación. La tanda sigue en el teléfono.";
                runOnUiThread(() -> { if (!isDestroyed()) render(message); });
            }
        });
    }

    private void writeOcrBlock(java.util.List<ArrayList<String>> parts, android.net.Uri destination,
                               TextView status) throws Exception {
        File staged = null;
        try {
                runOnUiThread(() -> status.setText("Completando las lecturas pendientes…"));
                ArrayList<String> photos = new ArrayList<>();
                JSONArray manifest = new JSONArray();
                for (ArrayList<String> group : parts) {
                    for (int i = 0; i < group.size(); i++) {
                        String photo = group.get(i);
                        photos.add(photo);
                        manifest.put(new JSONObject().put("texto", readOcr(photo)).put("certificado", i > 0));
                    }
                }
                runOnUiThread(() -> status.setText("Creando el archivo…"));
                // Termina el ZIP local antes de copiarlo al proveedor elegido para compartir.
                staged = File.createTempFile("partescan-", ".psocr", getCacheDir());
                try (OutputStream stream = java.nio.file.Files.newOutputStream(staged.toPath());
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
                try (OutputStream stream = getContentResolver().openOutputStream(destination, "wt")) {
                    if (stream == null) throw new java.io.IOException("Destino no disponible");
                    java.nio.file.Files.copy(staged.toPath(), stream);
                }
                runOnUiThread(() -> status.setText("Verificando la copia…"));
                try (java.io.InputStream saved = getContentResolver().openInputStream(destination);
                     java.io.InputStream original = java.nio.file.Files.newInputStream(staged.toPath())) {
                    if (saved == null || !java.util.Arrays.equals(exportDigest(original), exportDigest(saved))) {
                        throw new java.io.IOException("La copia guardada no coincide con la exportación local");
                    }
                }
        } finally {
            if (staged != null) staged.delete();
        }
    }

    private static byte[] exportDigest(java.io.InputStream stream)
            throws java.io.IOException, java.security.NoSuchAlgorithmException {
        java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[64 * 1024];
        int read;
        while ((read = stream.read(buffer)) != -1) digest.update(buffer, 0, read);
        return digest.digest();
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
        if (name == null) return;
        File cache = ocrCache(name);
        new File(folder, name).delete();
        new android.util.AtomicFile(cache).delete();
    }
}
