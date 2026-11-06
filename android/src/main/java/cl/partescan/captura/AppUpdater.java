package cl.partescan.captura;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import androidx.core.content.FileProvider;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.file.Files;

/** Consulta y descarga versiones firmadas del mismo paquete. Android confirma la instalación. */
final class AppUpdater {
    private final Activity activity;
    private static final String PREFIX = "https://github.com/gsnmartinh/partescan-v3/releases/download/";
    private boolean downloading;

    AppUpdater(Activity activity) { this.activity = activity; }

    private byte[] get(String url) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setConnectTimeout(15000); connection.setReadTimeout(30000);
        connection.setRequestProperty("User-Agent", "ParteScan-Captura");
        try (java.io.InputStream input = connection.getInputStream();
             java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream()) {
            byte[] buffer = new byte[32768]; int count;
            while ((count = input.read(buffer)) != -1) {
                if (output.size() + count > 120000000) throw new java.io.IOException("Descarga demasiado grande");
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        } finally { connection.disconnect(); }
    }

    void check() {
        new Thread(() -> {
            try {
                JSONObject release = new JSONObject(new String(get(
                        "https://api.github.com/repos/gsnmartinh/partescan-v3/releases/latest"),
                        java.nio.charset.StandardCharsets.UTF_8));
                JSONArray assets = release.getJSONArray("assets");
                String url = null; int remote = 0;
                for (int i = 0; i < assets.length(); i++) {
                    JSONObject asset = assets.getJSONObject(i);
                    String name = asset.getString("name");
                    java.util.regex.Matcher match = java.util.regex.Pattern.compile(
                            "ParteScan-Captura-(\\d+)\\.(\\d+)\\.(\\d+)\\.apk").matcher(name);
                    if (match.matches()) {
                        remote = Integer.parseInt(match.group(1))*1000000
                                + Integer.parseInt(match.group(2))*1000 + Integer.parseInt(match.group(3));
                        url = asset.getString("browser_download_url");
                    }
                }
                PackageInfo installed = activity.getPackageManager().getPackageInfo(activity.getPackageName(), 0);
                String[] v = installed.versionName.split("\\.");
                int current = Integer.parseInt(v[0])*1000000 + Integer.parseInt(v[1])*1000 + Integer.parseInt(v[2]);
                if (url == null || !url.startsWith(PREFIX) || remote <= current) return;
                final String downloadUrl = url;
                activity.runOnUiThread(() -> {
                    if (activity.isFinishing() || activity.isDestroyed()) return;
                    new AlertDialog.Builder(activity).setTitle("Actualización disponible")
                            .setMessage("Descargar la nueva versión de ParteScan Captura. Android pedirá confirmar la instalación.")
                            .setNegativeButton("Más tarde", null)
                            .setPositiveButton("Actualizar", (d,w) -> download(downloadUrl)).show();
                });
            } catch (Exception ignored) { /* La captura funciona sin conexión. */ }
        }).start();
    }

    private void download(String url) {
        if (downloading) return;
        downloading = true;
        android.widget.Toast.makeText(activity, "Descargando actualización…", android.widget.Toast.LENGTH_LONG).show();
        new Thread(() -> {
            try {
                File folder = new File(activity.getCacheDir(), "actualizaciones"); folder.mkdirs();
                File apk = new File(folder, "ParteScan-Captura.apk");
                Files.write(apk.toPath(), get(url));
                PackageManager manager = activity.getPackageManager();
                PackageInfo candidate = manager.getPackageArchiveInfo(apk.getPath(), PackageManager.GET_SIGNING_CERTIFICATES);
                PackageInfo installed = manager.getPackageInfo(activity.getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
                if (candidate == null || !activity.getPackageName().equals(candidate.packageName)
                        || candidate.getLongVersionCode() <= installed.getLongVersionCode()
                        || !java.util.Arrays.equals(candidate.signingInfo.getApkContentsSigners(),
                                                    installed.signingInfo.getApkContentsSigners())) {
                    throw new java.io.IOException("La actualización no corresponde a esta aplicación.");
                }
                activity.runOnUiThread(() -> {
                    try {
                        Uri uri = FileProvider.getUriForFile(activity, activity.getPackageName()+".fotos", apk);
                        Intent intent = new Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive");
                        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        activity.startActivity(intent);
                    } catch (Exception error) {
                        android.widget.Toast.makeText(activity, "Permite instalar actualizaciones de ParteScan Captura en Ajustes y vuelve a intentarlo.", android.widget.Toast.LENGTH_LONG).show();
                    }
                });
            } catch (Exception error) {
                activity.runOnUiThread(() -> android.widget.Toast.makeText(activity,
                        "No se pudo actualizar. " + error.getMessage(), android.widget.Toast.LENGTH_LONG).show());
            } finally { downloading = false; }
        }).start();
    }
}
