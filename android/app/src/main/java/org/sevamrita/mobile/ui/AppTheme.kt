package org.sevamrita.mobile.ui

import androidx.activity.ComponentActivity
import android.content.Context
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

internal val LocalAppDark = staticCompositionLocalOf { false }
internal object Appearance {
    val mode = mutableStateOf("Light")
    fun load(context: Context) { mode.value = context.getSharedPreferences("appearance",0).getString("mode","Light") ?: "Light" }
    fun set(context: Context, value: String) { require(value in listOf("Light","Dark","System"));context.getSharedPreferences("appearance",0).edit().putString("mode",value).apply();mode.value=value }
}

/** Semantic palette mapping for existing chat cards, keeping contrast in both modes. */
internal fun darkArgb(value: Long): Long {
    val r=(value shr 16 and 255).toInt();val g=(value shr 8 and 255).toInt();val b=(value and 255).toInt()
    val high=maxOf(r,g,b);val low=minOf(r,g,b)
    if (value==0xFFFFFFFFL) return 0xFF1B262D
    if (low>170 && high-low>=9) return when { r>g+8 -> 0xFF3A2630;b>r+6 -> 0xFF243349;g>r+5 -> 0xFF19382F;else -> 0xFF352F24 }
    if (high-low < 30) return when { low>220 -> 0xFF202D34;low>170 -> 0xFF41545F;high<105 -> 0xFFE7EFF3;else -> 0xFFB6C6CF }
    if (r>g*1.25 && r>b*1.1) return 0xFFFFAFBA
    if (b>r*1.15 && b>g*1.08) return 0xFFA7C8FF
    if (g>r*1.1 && g>b*.85) return 0xFF75DFC1
    if (r>g && g>b*1.15) return 0xFFF4D295
    return 0xFFBDCCD4
}
@Composable internal fun appColor(light: Long): Color = if(LocalAppDark.current) Color(darkArgb(light)).copy(alpha=((light shr 24) and 255)/255f) else Color(light)

@Composable internal fun SFTheme(content: @Composable () -> Unit) {
    val context=LocalContext.current
    val dark=when(Appearance.mode.value){"Dark"->true;"System"->isSystemInDarkTheme();else->false}
    SideEffect {
        (context as? ComponentActivity)?.enableEdgeToEdge(
            statusBarStyle=if(dark) SystemBarStyle.dark(android.graphics.Color.TRANSPARENT) else SystemBarStyle.light(android.graphics.Color.TRANSPARENT,android.graphics.Color.TRANSPARENT),
            navigationBarStyle=if(dark) SystemBarStyle.dark(0xFF111A20.toInt()) else SystemBarStyle.light(android.graphics.Color.WHITE,android.graphics.Color.WHITE))
        (context as? ComponentActivity)?.let { activity ->
            androidx.core.view.WindowCompat.getInsetsController(activity.window, activity.window.decorView).apply {
                isAppearanceLightStatusBars = !dark
                isAppearanceLightNavigationBars = !dark
            }
        }
    }
    val colors=if(dark) darkColorScheme(primary=Color(0xFF75DFC1),onPrimary=Color(0xFF092D23),
        background=Color(0xFF111A20),onBackground=Color(0xFFE7EFF3),surface=Color(0xFF1B262D),onSurface=Color(0xFFE7EFF3),
        onSurfaceVariant=Color(0xFFB6C6CF),secondaryContainer=Color(0xFF244238),onSecondaryContainer=Color(0xFFDAF8EC),
        error=Color(0xFFFFAFBA),outline=Color(0xFF8B9DA7),surfaceVariant=Color(0xFF293941))
    else lightColorScheme(primary=Color(0xFF08745E),onPrimary=Color.White,background=Color(0xFFF5F7F4),onBackground=Color(0xFF1D3035),
        surface=Color.White,onSurface=Color(0xFF1D3035),secondaryContainer=Color(0xFFE5F3ED),onSecondaryContainer=Color(0xFF1D3035))
    CompositionLocalProvider(LocalAppDark provides dark, LocalContentColor provides colors.onSurface) { MaterialTheme(colorScheme=colors,content=content) }
}
