package cl.partescan.captura;

import android.app.AlertDialog;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;
import java.io.File;
import java.io.FileOutputStream;
import java.util.ArrayList;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.GraphicsMode;
import org.robolectric.shadows.ShadowDialog;
import org.robolectric.util.ReflectionHelpers;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 34, qualifiers = "w393dp-h852dp-xxhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
public class NavigationTest {
    private ActivityController<MainActivity> controller;
    private MainActivity activity;

    @Before public void create() {
        controller = Robolectric.buildActivity(MainActivity.class).setup();
        activity = controller.get();
        list("pages").clear(); list("attachments").clear();
        ReflectionHelpers.setField(activity, "part", null);
        ReflectionHelpers.setField(activity, "certificate", null);
        ReflectionHelpers.setField(activity, "completedParts", 0);
        ReflectionHelpers.setField(activity, "editingIndex", -1);
        ReflectionHelpers.setField(activity, "undoDelete", null);
        navigate(0);
    }
    @After public void destroy() { controller.pause().stop().destroy(); }
    private <T> ArrayList<T> list(String field) { return ReflectionHelpers.getField(activity, field); }
    private View root() { return activity.findViewById(android.R.id.content); }
    private void navigate(int tab) { ReflectionHelpers.callInstanceMethod(activity, "navigate", ReflectionHelpers.ClassParameter.from(int.class, tab)); }
    private View byDescription(View view, String description) {
        if (description.contentEquals(view.getContentDescription() == null ? "" : view.getContentDescription())) return view;
        if (view instanceof ViewGroup) for (int i=0; i<((ViewGroup)view).getChildCount(); i++) {
            View found=byDescription(((ViewGroup)view).getChildAt(i), description); if (found!=null) return found;
        }
        return null;
    }
    private Button button(View view, String text) {
        if (view instanceof Button && text.contentEquals(((TextView)view).getText())) return (Button)view;
        if (view instanceof ViewGroup) for (int i=0; i<((ViewGroup)view).getChildCount(); i++) {
            Button found=button(((ViewGroup)view).getChildAt(i), text); if (found!=null) return found;
        }
        return null;
    }
    private void clickDescription(String value) { View v=byDescription(root(),value); assertNotNull(value,v); v.performClick(); }
    private void click(String value) { Button b=button(root(),value); assertNotNull(value,b); assertTrue(b.isEnabled()); b.performClick(); }

    private void photo(String name, String title) throws Exception {
        File folder=ReflectionHelpers.getField(activity,"folder");
        Bitmap bitmap=Bitmap.createBitmap(300,400,Bitmap.Config.ARGB_8888);
        Canvas canvas=new Canvas(bitmap); canvas.drawColor(Color.WHITE);
        Paint paint=new Paint(); paint.setColor(Color.rgb(15,108,189)); paint.setTextSize(18);
        canvas.drawText(title,20,45,paint);
        paint.setColor(Color.LTGRAY); paint.setStrokeWidth(2);
        for(int y=85;y<350;y+=24) canvas.drawLine(20,y,280,y,paint);
        try(FileOutputStream out=new FileOutputStream(new File(folder,name))) { bitmap.compress(Bitmap.CompressFormat.JPEG,90,out); }
        bitmap.recycle();
    }
    private void seed() throws Exception {
        photo("first.jpg","PARTE DE PRUEBA"); photo("cert.jpg","CERTIFICADO"); photo("second.jpg","SEGUNDO PARTE");
        list("pages").add("first.jpg"); list("pages").add("cert.jpg"); list("pages").add("second.jpg");
        list("attachments").add(1); ReflectionHelpers.setField(activity,"completedParts",2); navigate(0);
    }
    private void screenshot(String name) throws Exception {
        org.robolectric.Shadows.shadowOf(android.os.Looper.getMainLooper()).idle();
        float density=activity.getResources().getDisplayMetrics().density;
        int width=Math.round(activity.getResources().getConfiguration().screenWidthDp*density);
        int height=Math.round(activity.getResources().getConfiguration().screenHeightDp*density);
        View root=root(); root.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(height,View.MeasureSpec.EXACTLY)); root.layout(0,0,width,height);
        root.jumpDrawablesToCurrentState();
        root.getViewTreeObserver().dispatchOnPreDraw();
        Bitmap bitmap=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888); root.draw(new Canvas(bitmap));
        File directory=new File("build/test-screenshots"); directory.mkdirs();
        try(FileOutputStream output=new FileOutputStream(new File(directory,name+".png"))) { assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG,100,output)); }
        bitmap.recycle();
    }

    @Test public void emptyBatchHasFocusedActionsAndPersistentNavigation() throws Exception {
        assertNotNull(button(root(),"Escanear primer parte"));
        assertNull(button(root(),"Eliminar este parte"));
        screenshot("01-tanda-vacia");
        clickDescription("Escanear");
        assertNotNull(button(root(),"Escanear parte"));
        assertNull(button(root(),"Agregar certificado"));
        screenshot("02-escanear");
        clickDescription("Guardar");
        assertFalse(button(root(),"Guardar para ParteScan").isEnabled());
        clickDescription("Tanda");
        assertTrue(byDescription(root(),"Tanda").isSelected());
    }

    @Test public void reviewingAndSavingPreservesOrderAndCertificate() throws Exception {
        seed(); screenshot("03-tanda");
        clickDescription("Revisar parte 1, con certificado");
        assertEquals("first.jpg",ReflectionHelpers.getField(activity,"part"));
        assertEquals("cert.jpg",ReflectionHelpers.getField(activity,"certificate"));
        screenshot("04-revisar-parte");
        click("Guardar cambios");
        assertEquals("first.jpg",list("pages").get(0));
        assertEquals("cert.jpg",list("pages").get(1));
        assertEquals("second.jpg",list("pages").get(2));
        clickDescription("Guardar");
        assertTrue(button(root(),"Guardar para ParteScan").isEnabled());
        screenshot("05-guardar");
    }

    @Test public void deleteAndUndoRestoresThePartAndItsCertificate() throws Exception {
        seed(); clickDescription("Revisar parte 1, con certificado");
        ReflectionHelpers.callInstanceMethod(activity,"removeCurrent");
        ((AlertDialog)ShadowDialog.getLatestDialog()).getButton(AlertDialog.BUTTON_POSITIVE).performClick();
        org.robolectric.Shadows.shadowOf(android.os.Looper.getMainLooper()).idle();
        assertEquals(1,((Integer)ReflectionHelpers.getField(activity,"completedParts")).intValue());
        click("Deshacer eliminación");
        assertEquals(2,((Integer)ReflectionHelpers.getField(activity,"completedParts")).intValue());
        assertEquals("first.jpg",list("pages").get(0));
        assertEquals("cert.jpg",list("pages").get(1));
        assertEquals(Integer.valueOf(1),list("attachments").get(0));
    }

    @Test public void recreationKeepsThePartBeingReviewed() throws Exception {
        seed(); clickDescription("Revisar parte 1, con certificado");
        controller.recreate(); activity=controller.get();
        assertEquals("first.jpg",ReflectionHelpers.getField(activity,"part"));
        assertEquals("cert.jpg",ReflectionHelpers.getField(activity,"certificate"));
        assertNotNull(button(root(),"Guardar cambios"));
        clickDescription("Tanda");
        assertEquals(3,list("pages").size());
    }

    @Test public void systemBackReturnsToBatchWithoutLosingTheReviewedPart() throws Exception {
        seed(); clickDescription("Revisar parte 1, con certificado");
        android.window.OnBackInvokedCallback back = ReflectionHelpers.getField(activity,"systemBackCallback");
        assertNotNull(back);
        ReflectionHelpers.setField(activity,"busy",true);
        back.onBackInvoked();
        assertTrue(byDescription(root(),"Escanear").isSelected());
        ReflectionHelpers.setField(activity,"busy",false);
        back.onBackInvoked();
        assertTrue(byDescription(root(),"Tanda").isSelected());
        assertEquals("first.jpg",list("pages").get(0));
        assertEquals("cert.jpg",list("pages").get(1));
        assertFalse(activity.isFinishing());
        clickDescription("Guardar"); back.onBackInvoked();
        assertTrue(byDescription(root(),"Tanda").isSelected());
    }

    @Test @Config(qualifiers="w320dp-h640dp-mdpi") public void smallScreenKeepsNavigationAndMainActionVisible() throws Exception {
        seed(); clickDescription("Revisar parte 1, con certificado");
        screenshot("06-pantalla-pequena");
        View nav=byDescription(root(),"Tanda"); int[] position=new int[2]; nav.getLocationOnScreen(position);
        assertTrue(position[1]+nav.getHeight()<=root().getHeight());
        Button primary=button(root(),"Guardar cambios"); primary.getLocationOnScreen(position);
        assertTrue(position[1]+primary.getHeight()<=root().getHeight());
    }

    @Test @Config(qualifiers="w393dp-h852dp-night-xxhdpi") public void darkThemeUsesSameNavigation() throws Exception {
        seed(); screenshot("07-tanda-oscura");
        clickDescription("Guardar"); screenshot("08-guardar-oscuro");
        FluentStyle style=ReflectionHelpers.getField(activity,"fluent"); assertTrue(style.dark);
        assertTrue(byDescription(root(),"Guardar").isSelected());
    }
}
