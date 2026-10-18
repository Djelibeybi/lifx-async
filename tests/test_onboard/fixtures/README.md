# Fake access point credentials

`lifx-fake-ap.crt` and `lifx-fake-ap.key` are a synthetic self-signed RSA
certificate and private key for the in-process fake LIFX SoftAP that the
`tests/test_onboard` suite starts on the loopback interface. They are test-only
credentials: the common name is `lifx-fake-ap`, nothing trusts them, they are
not installed anywhere, and they protect nothing. Anyone may read them.

They are committed because the standard library cannot mint a certificate at
runtime, and the key is RSA so the `AES256-SHA` RSA key-exchange suite can
negotiate under TLS 1.0 for the legacy handshake test.

They were generated once with:

```
openssl req -x509 -newkey rsa:2048 -nodes -keyout lifx-fake-ap.key \
  -out lifx-fake-ap.crt -days 36500 -subj "/CN=lifx-fake-ap"
```

The `detect-private-key` pre-commit hook excludes this directory for that reason.
