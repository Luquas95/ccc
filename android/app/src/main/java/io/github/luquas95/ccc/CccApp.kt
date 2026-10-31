package io.github.luquas95.ccc

import android.app.Application
import android.content.Context
import io.github.luquas95.ccc.data.Language

/** Only to give the application context the app's own language (see [Language]). */
class CccApp : Application() {
    override fun attachBaseContext(base: Context) = super.attachBaseContext(Language.wrap(base))
}
