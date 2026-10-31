package io.github.luquas95.ccc.data

import android.content.Context
import android.content.res.Configuration
import java.util.Locale

/** The languages the app is translated into: the choice in the Connection screen ("" = follow the phone). */
object Language {
    val CHOICES = listOf("en" to "English", "cs" to "Čeština")

    /** The chosen language; null = follow the phone (the default locale is then the phone's again). */
    private fun locale(context: Context): Locale? {
        val tag = Settings(context).language
        val locale = if (tag.isBlank()) android.content.res.Resources.getSystem().configuration.locales[0]
        else Locale.forLanguageTag(tag)
        Locale.setDefault(locale) // also the Accept-Language ccc answers in
        return locale.takeIf { tag.isNotBlank() }
    }

    /** After a change: the long-lived application context (the ViewModel's texts) follows too. */
    @Suppress("DEPRECATION")
    fun apply(app: android.app.Application) {
        val locale = locale(app) ?: android.content.res.Resources.getSystem().configuration.locales[0]
        val config = Configuration(app.resources.configuration)
        config.setLocale(locale)
        app.resources.updateConfiguration(config, app.resources.displayMetrics)
    }

    /** [context] with the app's chosen language, or itself when it follows the phone. */
    fun wrap(context: Context): Context {
        val locale = locale(context) ?: return context
        val config = Configuration(context.resources.configuration)
        config.setLocale(locale)
        return context.createConfigurationContext(config)
    }
}
