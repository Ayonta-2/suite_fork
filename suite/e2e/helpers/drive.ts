import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { frappeData } from "./frappe";

export interface DriveEntity {
	name: string;
	file_name: string;
	is_folder: boolean | number;
}

async function driveEntities(
	request: APIRequestContext,
): Promise<DriveEntity[]> {
	const response = await request.get("/api/method/suite.drive.api.list.files");
	return frappeData<DriveEntity[]>(response);
}

export async function waitForDriveEntity(
	request: APIRequestContext,
	fileName: string,
): Promise<DriveEntity> {
	let entity: DriveEntity | undefined;
	await expect
		.poll(async () => {
			entity = (await driveEntities(request)).find(
				(candidate) => candidate.file_name === fileName,
			);
			return entity?.name;
		})
		.toBeTruthy();
	return entity as DriveEntity;
}

export async function setDriveAccess(
	request: APIRequestContext,
	entityName: string,
	user: string,
): Promise<void> {
	const response = await request.post(
		"/api/method/suite.drive.api.files.update_access",
		{
			form: {
				entity_name: entityName,
				method: "share",
				user,
				read: 1,
				comment: 1,
				share: 0,
				write: 0,
				upload: 0,
			},
		},
	);
	await frappeData(response);
}

export async function openEntityActions(page: Page, entityName: string) {
	await page.getByTestId(`drive-entity-actions-${entityName}`).click();
}
