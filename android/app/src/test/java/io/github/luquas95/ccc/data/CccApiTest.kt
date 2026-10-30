package io.github.luquas95.ccc.data

import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpServer
import java.net.InetSocketAddress
import java.util.concurrent.CopyOnWriteArrayList
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/** CccApi against a small fake of ccc's API (the JDK's own HTTP server). */
class CccApiTest {
    private data class Seen(val method: String, val uri: String, val auth: String?, val body: String)

    private lateinit var server: HttpServer
    private val seen = CopyOnWriteArrayList<Seen>()
    private val answers = mutableMapOf<String, Pair<Int, String>>()

    @Before
    fun start() {
        server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
        server.createContext("/api/v1/") { exchange -> handle(exchange) }
        server.start()
    }

    @After
    fun stop() = server.stop(0)

    private fun handle(exchange: HttpExchange) {
        val body = exchange.requestBody.readBytes().decodeToString()
        seen += Seen(exchange.requestMethod, exchange.requestURI.toString(), exchange.requestHeaders.getFirst("Authorization"), body)
        val path = exchange.requestURI.path.removePrefix("/api/v1/")
        if (path == "events") {
            exchange.responseHeaders.add("Content-Type", "text/event-stream")
            exchange.sendResponseHeaders(200, 0)
            exchange.responseBody.use {
                it.write(": connected\n\nevent: changed\ndata: {\"conversations\": [3], \"removed\": [4]}\n\n".toByteArray())
                it.flush()
            }
            return
        }
        val (code, answer) = answers[path] ?: (404 to """{"error": "Not found."}""")
        val bytes = answer.toByteArray()
        exchange.sendResponseHeaders(code, bytes.size.toLong())
        exchange.responseBody.use { it.write(bytes) }
    }

    private fun api(token: String = "secret") = CccApi("http://127.0.0.1:${server.address.port}", token)

    @Test
    fun `reads the context fill and the git state of a conversation`() = runBlocking {
        answers["conversations"] = 200 to """[{"id": 1, "name": "shop", "path": "/p", "status": "idle",
            "delivery_mode": "interactive", "context": {"tokens": 186000, "percent": 93, "level": "danger"},
            "git": {"branch": "feature-x", "added": 12, "removed": 3, "ahead": 2, "behind": 0}},
            {"id": 2, "name": "docs", "path": "/d", "status": "idle", "delivery_mode": "headless",
            "context": null, "git": null}]"""

        val (shop, docs) = api().conversations()

        assertEquals("93 %", shop.context?.text)
        assertEquals("danger", shop.context?.level)
        assertEquals("feature-x +12−3 ↑2", shop.git?.text)
        assertNull(docs.context)
        assertNull(docs.git)
    }

    @Test
    fun `reads the list with the token`() = runBlocking {
        answers["conversations"] = 200 to """[{"id": 1, "name": "shop", "path": "/p", "status": "blocked_error",
            "delivery_mode": "interactive", "pending": 2, "needs_approval": true, "last_error": "boom",
            "group": {"key": "own:Release", "title": "Release"}, "something_new": 1}]"""

        val list = api().conversations()

        assertEquals("Bearer secret", seen.single().auth)
        assertEquals(1, list.size)
        assertEquals(ConversationStatus.BLOCKED_ERROR, list[0].state)
        assertEquals(2, list[0].pending)
        assertEquals("Release", list[0].group?.title)
    }

    @Test
    fun `messages ask for what is new`() = runBlocking {
        answers["conversations/7/messages"] = 200 to """{"total": 3, "messages": [
            {"index": 2, "kind": "assistant_text", "text": "Done", "time": "2026-10-21T10:00:00+00:00"}]}"""

        val messages = api().messages(7, after = 1)

        assertEquals("/api/v1/conversations/7/messages?after=1&limit=100", seen.single().uri)
        assertEquals(listOf("Done"), messages.messages.map { it.text })
    }

    @Test
    fun `send and decide post JSON`() = runBlocking {
        answers["conversations/7/messages"] = 201 to """{"id": 9, "text": "go on"}"""
        answers["permissions/5"] = 200 to """{"id": 5, "decision": "always"}"""

        api().send(7, "go on")
        api().decide(5, "always")

        assertEquals(listOf("POST", "POST"), seen.map { it.method })
        assertEquals("""{"text":"go on"}""", seen[0].body)
        assertEquals("""{"decision":"always"}""", seen[1].body)
    }

    @Test
    fun `an error carries ccc's message and code`() = runBlocking {
        answers["status"] = 401 to """{"error": "Missing or wrong API token."}"""
        try {
            api("wrong").status()
            fail("no error")
        } catch (e: ApiException) {
            assertEquals(401, e.code)
            assertEquals("Missing or wrong API token.", e.message)
        }
    }

    @Test
    fun `unknown usage is null`() = runBlocking {
        answers["usage"] = 200 to "null"
        assertNull(api().usage())
    }

    @Test
    fun `the events stream says connected, then what changed`() = runBlocking {
        val events = api().events().take(2).toList()
        assertEquals(ServerEvent.Connected, events[0])
        assertEquals(ServerEvent.Changed(Change(listOf(3), listOf(4))), events[1])
    }

    @Test
    fun `a refused events stream is an error`() = runBlocking {
        server.removeContext("/api/v1/")
        server.createContext("/api/v1/") { exchange ->
            val bytes = """{"error": "Missing or wrong API token."}""".toByteArray()
            exchange.sendResponseHeaders(401, bytes.size.toLong())
            exchange.responseBody.use { it.write(bytes) }
        }
        try {
            api().events().first()
            fail("no error")
        } catch (e: ApiException) {
            assertEquals(401, e.code)
        }
    }

    @Test
    fun `the address as typed`() {
        assertEquals("https://pc.tail.ts.net/api/v1/", CccApi.baseUrl("pc.tail.ts.net").toString())
        assertEquals("https://pc.tail.ts.net/api/v1/", CccApi.baseUrl(" https://pc.tail.ts.net/ ").toString())
        assertEquals("http://10.0.2.2:8737/api/v1/", CccApi.baseUrl("http://10.0.2.2:8737/api/v1").toString())
        assertNull(CccApi.baseUrl(""))
        assertTrue(CccApi.baseUrl("not an address") == null)
    }
}
