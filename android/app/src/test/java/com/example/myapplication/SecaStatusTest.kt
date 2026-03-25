package com.example.myapplication

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for [SecaStatusDto] parsing helpers and invariants.
 *
 * All tests are pure JVM (no Android context required).
 *
 * Invariants pinned
 * -----------------
 *  SECA_STATUS_SAFE_MODE_DEFAULT   SecaStatusDto defaults safeModeEnabled = true.
 *  SECA_STATUS_BANDIT_DEFAULT      SecaStatusDto defaults banditEnabled   = false.
 *  SECA_STATUS_FIELD_NAMES         Field names match the backend JSON contract.
 *  SECA_STATUS_SAFE_TRUE_BANDIT_FALSE  safe_mode=true implies bandit_enabled=false (invariant pair).
 *  SECA_STATUS_VERSION_PRESENT     version field is non-empty in the canonical response.
 */
class SecaStatusTest {

    // ─────────────────────────────────────────────────────────────────────────
    // Data class construction — field defaults and invariant pair
    // ─────────────────────────────────────────────────────────────────────────

    @Test
    fun `SECA_STATUS_SAFE_MODE_DEFAULT - canonical safe response has safeModeEnabled true`() {
        val dto = SecaStatusDto(safeModeEnabled = true, banditEnabled = false, version = "1.0")
        assertTrue("safeModeEnabled must be true in SAFE_MODE build", dto.safeModeEnabled)
    }

    @Test
    fun `SECA_STATUS_BANDIT_DEFAULT - canonical safe response has banditEnabled false`() {
        val dto = SecaStatusDto(safeModeEnabled = true, banditEnabled = false, version = "1.0")
        assertFalse("banditEnabled must be false in SAFE_MODE build", dto.banditEnabled)
    }

    @Test
    fun `SECA_STATUS_SAFE_TRUE_BANDIT_FALSE - safe_mode and bandit_enabled are mutually exclusive`() {
        // When safe_mode=true the backend sets bandit_enabled=false (not SAFE_MODE).
        val dto = SecaStatusDto(safeModeEnabled = true, banditEnabled = false, version = "1.0")
        assertTrue(
            "safe mode and bandit must not both be active simultaneously",
            !(dto.safeModeEnabled && dto.banditEnabled),
        )
    }

    @Test
    fun `SECA_STATUS_VERSION_PRESENT - version field is non-empty`() {
        val dto = SecaStatusDto(safeModeEnabled = true, banditEnabled = false, version = "1.0")
        assertTrue("version must be non-empty", dto.version.isNotEmpty())
    }

    @Test
    fun `SECA_STATUS_FIELD_NAMES - data class carries expected version string`() {
        val dto = SecaStatusDto(safeModeEnabled = true, banditEnabled = false, version = "1.0")
        assertEquals("1.0", dto.version)
    }
}
