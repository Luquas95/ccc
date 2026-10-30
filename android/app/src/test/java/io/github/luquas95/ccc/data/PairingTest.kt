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
    fun `refuses an address that is not https or a private one, or that has a user in it`() {
        fun invite(server: String) = Pairing.parse("ccc://pair?server=${java.net.URLEncoder.encode(server, "UTF-8")}&code=abc")
        assertNull(invite("http://evil.example.com"))
        assertNull(invite("https://user:pw@evil.example.com"))
        assertNull(invite("https://good.example.com@evil.example.com"))
        assertNull(invite("ftp://x.ts.net"))
        assertEquals("http://100.64.0.7:8737", invite("http://100.64.0.7:8737")?.server)
        assertEquals("https://xia.tail0ffcfb.ts.net:8737", invite("https://xia.tail0ffcfb.ts.net:8737")?.server)
        assertNull(invite("http://8.8.8.8:8737"))
        assertNull(invite("https://xia.ts.net/somewhere/else"))
        assertNull(invite("https://xia.ts.net/?next=evil"))
        assertNull(invite("https://xia.ts.net/#evil"))
        assertEquals("https://xia.ts.net/api/v1", invite("https://xia.ts.net/api/v1")?.server)
    }

    @Test
    fun `the origin shown is the one the app connects to, port included`() {
        assertEquals("https://xia.ts.net:443", Pairing.origin("https://xia.ts.net"))
        assertEquals("https://xia.ts.net:8737", Pairing.origin("https://xia.ts.net:8737/api/v1/"))
        assertEquals("https://xia.ts.net:443", Pairing.origin("xia.ts.net"))
        assertEquals("http://100.64.0.7:8737", Pairing.origin("http://100.64.0.7:8737"))
        assertNull(Pairing.origin(""))
    }

    @Test
    fun `refuses any other QR code`() {
        assertNull(Pairing.parse("https://example.com/?server=x&code=y"))
        assertNull(Pairing.parse("ccc://pair?server=https%3A%2F%2Fx.ts.net"))
        assertNull(Pairing.parse("ccc://pair?server=&code=abc"))
        assertNull(Pairing.parse(""))
    }
}
