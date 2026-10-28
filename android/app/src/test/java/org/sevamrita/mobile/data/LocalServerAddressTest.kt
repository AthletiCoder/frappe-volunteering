package org.sevamrita.mobile.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalServerAddressTest {
    @Test fun acceptsPrivateWifiAndEmulatorAddresses() {
        listOf("192.168.1.18", "10.0.2.2", "10.20.30.40", "172.16.0.4", "172.31.255.254")
            .forEach { assertTrue(it, isPrivateIpv4(it)) }
    }

    @Test fun rejectsPublicOrMalformedAddresses() {
        listOf("", "localhost", "127.0.0.1", "8.8.8.8", "172.32.0.1", "192.168.1.300",
            "192.168.1.1:8001", "http://192.168.1.1", "192.168.1.-1", "192.168.1.1/path")
            .forEach { assertFalse(it, isPrivateIpv4(it)) }
    }
}
