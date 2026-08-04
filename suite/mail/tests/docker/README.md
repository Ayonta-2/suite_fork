# Stalwart for mail/calendar integration tests

The backend tests in `suite/mail/tests/` and `suite/calendar/tests/` run against a live
Stalwart server. Test classes skip themselves when Stalwart is not configured, so a
plain `bench run-tests --app suite` stays green without it.

## Start Stalwart

```sh
cd apps/suite/suite/mail/tests/docker
./start-stalwart.sh
```

This boots `stalwartlabs/stalwart` on `http://127.0.0.1:8080` with recovery admin
`admin:admin`, applies `bootstrap.ndjson` through `stalwart-cli` (downloaded on the
fly), and restarts the container — the same sequence the production deploy playbook
performs. Override with `STALWART_VERSION`, `STALWART_CLI_VERSION`,
`STALWART_ADMIN_USER`, `STALWART_ADMIN_PASSWORD`, or `STALWART_HTTP_PORT`.

## Point the site at it

```sh
bench --site <site> set-config allow_tests true
bench --site <site> set-config mail "{'server_url': 'http://127.0.0.1:8080', 'username': 'admin', 'password': 'admin', 'verify_ssl': 0, 'root_domain_name': 'example.test'}" --parse
```

(`Mail Settings` takes priority over `site_config.json` — leave its Stalwart fields
empty on test sites.)

## Run the tests

```sh
bench --site <site> run-tests --app suite --module suite.mail.tests.test_admin_members
```

Test data uses unique per-run names, so repeated runs against the same container are
fine. For a full reset:

```sh
docker compose down -v && ./start-stalwart.sh
```
