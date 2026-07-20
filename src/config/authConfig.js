/**
 * PILOT-ONLY access allowlist — this file is temporary routing data, not the security boundary.
 *
 * Real enforcement lives in Firebase Security Rules (database.rules.json), which currently
 * authorize ~11 UIDs for branch2 while this file lists far fewer emails. Any signed-in user whose
 * email is missing here gets NO branch assignment and is held on the login page with an
 * "account not assigned" message (LoginPage.jsx) — they are never navigated to a branch they
 * cannot access. If a production tester sees that message, add their email to the matching
 * branch below AND confirm the same account is authorized in database.rules.json.
 *
 * Production evolution (do not implement during the pilot): derive branch assignment from a
 * single source the backend controls — Firebase custom claims or an RTDB /users/{uid}/branch
 * record — so rules and routing can never drift apart. This file then disappears.
 */
export const AUTH_CONFIG = {
    adminEmail: 'fitzhofer@gmail.com',
    branches: {
        // branch1 was decommissioned after pilot testing; branch2 is the only operational branch.
        branch2: {
            emails: ['doralyncascato3@gmail.com', 'dummy@dummy.com'],
            name: 'Sugar Cafe Nivel Hills'
        }
    }
};

export function isUserAdmin(email) {
    return email === AUTH_CONFIG.adminEmail;
}

export function getUserBranch(email) {
    if (isUserAdmin(email)) return 'admin';
    return Object.keys(AUTH_CONFIG.branches).find(
        id => {
            const b = AUTH_CONFIG.branches[id];
            return (b.emails && b.emails.includes(email)) || b.email === email;
        }
    );
}

export function canAccessBranch(email, requestedBranchId) {
    if (isUserAdmin(email)) return true;
    const b = AUTH_CONFIG.branches[requestedBranchId];
    if (!b) return false;
    return (b.emails && b.emails.includes(email)) || b.email === email;
}
