package io.github.luquas95.ccc.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** The QR payload of src/ccc/pairing.py `payload`. */
class PairingTest {
    @Test
    fun `reads the address and the code of a ccc QR code`() {
        val invite = Pairing.parse("ccc://pair?server=https%3A%2F%2Fxia.tail0ffcfb.ts.net%3A8737&code=AbC_-0123")
        assertEquals(PairingInvite("https://xia.tail0ffcfb.ts.net:8737", "AbC_-0123"), invite)
    }

    @Test
    fun `refuses any other QR code`() {
        assertNull(Pairing.parse("https://example.com/?server=x&code=y"))
        assertNull(Pairing.parse("ccc://pair?server=https%3A%2F%2Fx.ts.net"))
        assertNull(Pairing.parse("ccc://pair?server=&code=abc"))
        assertNull(Pairing.parse(""))
    }
}
