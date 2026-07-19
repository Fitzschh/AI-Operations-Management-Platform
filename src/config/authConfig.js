export const AUTH_CONFIG = {
    adminEmail: 'fitzhofer@gmail.com',
    branches: {
        branch1: {
            email: 'pamaybay88@gmail.com',
            name: 'Branch 1'
        },
        branch2: {
            emails: ['doralyncascato3@gmail.com'],
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
