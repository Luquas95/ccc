package io.github.luquas95.ccc.data

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import io.github.luquas95.ccc.R
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

/** The app's own language is independent of the phone's (and of ccc's on the computer). */
@RunWith(AndroidJUnit4::class)
class LanguageTest {
    private val app: Application get() = ApplicationProvider.getApplicationContext()

    private fun text(language: String): String {
        Settings(app).language = language
        return Language.wrap(app).getString(R.string.app_language)
    }

    @Config(qualifiers = "cs")
    @Test fun englishInAppOnCzechPhone() = assertEquals("Language", text("en"))

    @Config(qualifiers = "en")
    @Test fun czechInAppOnEnglishPhone() = assertEquals("Jazyk", text("cs"))

    @Config(qualifiers = "cs")
    @Test fun followsPhoneWhenEmpty() = assertEquals("Jazyk", text(""))

    @Config(qualifiers = "cs")
    @Test fun applicationContextFollowsAfterChange() {
        Settings(app).language = "en"
        Language.apply(app)
        assertEquals("Language", app.getString(R.string.app_language))
        assertEquals("en", java.util.Locale.getDefault().language)
    }
}
