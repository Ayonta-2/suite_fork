import type { APIRequestContext } from "@playwright/test";

export interface Credentials {
	email: string;
	password: string;
}

export async function loginViaApi(
	request: APIRequestContext,
	credentials: Credentials,
): Promise<void> {
	const response = await request.post("/api/method/login", {
		form: { usr: credentials.email, pwd: credentials.password },
	});
	if (!response.ok()) {
		throw new Error(
			`Login failed for ${credentials.email} with status ${response.status()}`,
		);
	}
}
