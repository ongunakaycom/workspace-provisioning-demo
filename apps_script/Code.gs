/**
 * Sheet-driven provisioning — the version an admin can run without a pipeline.
 *
 * Setup:
 *   1. Sheet "Requests" with headers:
 *      email | first_name | last_name | org_unit | groups | status
 *      groups: comma separated, e.g. "eng-core,new-hires"
 *   2. Services → Admin SDK (AdminDirectory advanced service) enabled.
 *   3. A "Log" sheet, or this creates one on first run.
 *   4. Keep DRY_RUN = true until the log matches what you expect.
 *
 * Deliberately smaller than the Python version: no policy file, no snapshot
 * diffing. It reads the live directory per row and plans from the difference.
 */

const DRY_RUN = true;
const LEAVERS_OU = '/Leavers';
const ALLOWED_OUS = ['/Engineering', '/Operations', '/Leavers'];
const LOG_SHEET = 'Log';

function syncDirectory() {
  const sheet = SpreadsheetApp.getActive().getSheetByName('Requests');
  const rows = sheet.getDataRange().getValues();
  const headers = rows.shift().map(String);
  const col = (name) => headers.indexOf(name);

  const plan = [];
  rows.forEach((row, index) => {
    if (!row[col('email')]) return;
    const request = {
      email: String(row[col('email')]).trim(),
      firstName: String(row[col('first_name')] || '').trim(),
      lastName: String(row[col('last_name')] || '').trim(),
      orgUnit: String(row[col('org_unit')] || '').trim(),
      groups: String(row[col('groups')] || '')
        .split(',')
        .map((group) => group.trim())
        .filter(Boolean),
      status: String(row[col('status')] || 'active').trim().toLowerCase(),
      rowNumber: index + 2,
    };

    if (!isAllowedOu(request.orgUnit)) {
      plan.push({ kind: 'REFUSED', target: request.email, detail: `org unit ${request.orgUnit} not allowed` });
      return;
    }

    const existing = findUser(request.email);
    if (request.status === 'leaver') {
      plan.push(...planLeaver(request, existing));
    } else {
      plan.push(...planJoiner(request, existing));
    }
  });

  plan.forEach((action) => {
    if (action.kind !== 'REFUSED' && !DRY_RUN) execute(action);
    log([action.kind, action.target, action.detail, DRY_RUN ? 'planned' : 'applied']);
  });

  if (plan.length === 0) {
    log(['-', '-', 'directory already matches the sheet', DRY_RUN ? 'planned' : 'applied']);
  }
}

function planJoiner(request, existing) {
  const actions = [];

  if (!existing) {
    actions.push({
      kind: 'create_user',
      target: request.email,
      detail: `${request.firstName} ${request.lastName} -> ${request.orgUnit}`,
      payload: {
        primaryEmail: request.email,
        name: { givenName: request.firstName, familyName: request.lastName },
        orgUnitPath: request.orgUnit,
        changePasswordAtNextLogin: true,
      },
    });
    // A user created with an OU already set needs no move, but still needs
    // the group memberships the request asks for.
    request.groups.forEach((group) => actions.push({ kind: 'add_to_group', target: group, detail: request.email }));
    return actions;
  }

  if (existing.suspended) {
    actions.push({ kind: 'unsuspend_user', target: request.email, detail: 'returning hire' });
  }

  if (existing.orgUnitPath !== request.orgUnit) {
    actions.push({
      kind: 'move_user',
      target: request.email,
      detail: `${existing.orgUnitPath} -> ${request.orgUnit}`,
      payload: { orgUnitPath: request.orgUnit },
    });
  }

  const currentGroups = listGroups(request.email);
  request.groups
    .filter((group) => currentGroups.indexOf(group) === -1)
    .forEach((group) => actions.push({ kind: 'add_to_group', target: group, detail: request.email }));

  return actions;
}

function planLeaver(request, existing) {
  if (!existing) return [];
  const actions = [];

  // Suspend first: if this dies halfway, sign-in is already blocked and the
  // remaining steps are housekeeping that can be re-run safely.
  if (!existing.suspended) {
    actions.push({ kind: 'suspend_user', target: request.email, detail: 'block sign-in first' });
  }

  if (existing.orgUnitPath !== LEAVERS_OU) {
    actions.push({
      kind: 'move_user',
      target: request.email,
      detail: `${existing.orgUnitPath} -> ${LEAVERS_OU}`,
      payload: { orgUnitPath: LEAVERS_OU },
    });
  }

  listGroups(request.email).forEach((group) =>
    actions.push({ kind: 'remove_from_group', target: group, detail: request.email })
  );

  // Licences are not reclaimed here: Drive transfer and any legal hold come first.
  return actions;
}

function execute(action) {
  switch (action.kind) {
    case 'create_user':
      return AdminDirectory.Users.insert(action.payload);
    case 'move_user':
      return AdminDirectory.Users.update({ orgUnitPath: action.payload.orgUnitPath }, action.target);
    case 'suspend_user':
      return AdminDirectory.Users.update({ suspended: true }, action.target);
    case 'unsuspend_user':
      return AdminDirectory.Users.update({ suspended: false }, action.target);
    case 'add_to_group':
      return AdminDirectory.Members.insert({ email: action.detail }, action.target);
    case 'remove_from_group':
      return AdminDirectory.Members.remove(action.target, action.detail);
    default:
      throw new Error(`unknown action kind ${action.kind}`);
  }
}

function findUser(email) {
  try {
    return AdminDirectory.Users.get(email);
  } catch (error) {
    if (String(error).indexOf('404') !== -1) return null;
    throw error;
  }
}

function listGroups(email) {
  try {
    const response = AdminDirectory.Groups.list({ userKey: email });
    return (response.groups || []).map((group) => group.email);
  } catch (error) {
    return [];
  }
}

function isAllowedOu(orgUnit) {
  return ALLOWED_OUS.some((allowed) => orgUnit === allowed || orgUnit.indexOf(`${allowed}/`) === 0);
}

function log(row) {
  const book = SpreadsheetApp.getActive();
  const sheet = book.getSheetByName(LOG_SHEET) || book.insertSheet(LOG_SHEET);
  sheet.appendRow([new Date(), ...row]);
}
