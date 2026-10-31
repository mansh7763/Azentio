"""Exact header mapping: normalised names and aliases only. An unknown column stays unmapped and is reported."""

import re

from app.schemas import Account, Application, Claim, Customer, LoginEvent, Transaction

SCHEMAS = {
    "customers": Customer, "accounts": Account, "transactions": Transaction,
    "logins": LoginEvent, "applications": Application, "claims": Claim,
}

_SHARED = {
    "customer_id": ["custid", "clientid", "customerno", "customernumber", "custno"],
    "account_id": ["acctid", "accountno", "accountnumber", "acctno"],
    "timestamp": ["time", "datetime", "eventtime", "eventtimestamp", "createdat"],
    "device_id": ["device", "devicefingerprint"],
    "ip": ["ipaddress", "sourceip"],
    "phone": ["mobile", "mobileno", "phoneno", "phonenumber", "contactnumber", "contactno"],
    "email": ["emailaddress", "emailid"],
    "name": ["fullname", "customername"],
    "dob": ["dateofbirth", "birthdate"],
    "product": ["producttype", "accounttype"],
    "currency": ["ccy", "currencycode"],
    "segment": ["customersegment"],
    "onboarding_date": ["onboardeddate", "onboardedat", "joindate"],
    "open_date": ["openedon", "accountopendate"],
    "balance": ["currentbalance", "availablebalance"],
}

_BY_ENTITY = {
    "transactions": {
        "txn_id": ["transactionid", "transid", "tranid", "referenceno"],
        "sender_account": ["senderaccountid", "senderaccountno", "sender", "fromaccount", "sourceaccount",
                           "debitaccount", "accountid", "accountno", "accountnumber"],
        "beneficiary_account": ["beneficiaryaccountid", "beneficiaryaccountno", "beneficiary", "beneficiaryid",
                                "toaccount", "receiveraccount", "destinationaccount", "creditaccount", "payeeaccount"],
        "beneficiary_name": ["payeename", "receivername"],
        "amount": ["amt", "txnamount", "transactionamount"],
        "timestamp": ["txntime", "txndate", "transactiontime", "transactiondate", "date"],
        "type": ["txntype", "transactiontype", "direction"],
        "status": ["txnstatus", "transactionstatus"],
        "channel": ["txnchannel", "transactionchannel"],
    },
    "logins": {
        "event_id": ["loginid", "logid"],
        "timestamp": ["logintime", "logintimestamp", "date"],
        "outcome": ["status", "result", "authoutcome", "authresult", "loginstatus", "authenticationoutcome"],
        "event_type": ["action", "activity"],
    },
    "applications": {
        "application_id": ["appid", "applicationno", "loanapplicationid", "loanid"],
        "amount": ["loanamount", "requestedamount"],
        "timestamp": ["applicationdate", "applicationtime", "appliedat", "submittedat"],
        "disbursement_account": ["payoutaccount", "disbursementaccountid"],
    },
    "claims": {
        "amount": ["claimamount"],
        "incident_date": ["incidenttime", "lossdate"],
        "timestamp": ["claimdate", "filedat"],
        "payout_account": ["payoutaccountid", "beneficiaryaccount"],
    },
}


def normalise(column: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(column).lower())


def required_fields(entity: str) -> set[str]:
    return {name for name, field in SCHEMAS[entity].model_fields.items() if field.is_required()}


def _lookup(entity: str) -> dict[str, str]:
    fields = SCHEMAS[entity].model_fields
    table: dict[str, str] = {}
    for source in (_SHARED, _BY_ENTITY.get(entity, {})):  # entity aliases win over shared ones
        for canonical, aliases in source.items():
            if canonical in fields:
                table.update({alias: canonical for alias in aliases})
    table.update({normalise(name): name for name in fields})  # a real field name always wins
    return table


def map_columns(entity: str, columns: list[str], override: dict[str, str] | None = None) -> tuple[dict[str, str], list[str]]:
    """Returns (source column -> canonical field, columns left unmapped)."""
    override = override or {}
    unknown = sorted(set(override.values()) - set(SCHEMAS[entity].model_fields))
    if unknown:
        raise ValueError(f"mapping targets unknown {entity} fields: {', '.join(unknown)}")
    lookup = _lookup(entity)
    mapped = {source: target for source, target in override.items() if source in columns}
    taken = set(mapped.values())
    unmapped = []
    for column in columns:
        if column in mapped:
            continue
        target = lookup.get(normalise(column))
        if target and target not in taken:
            mapped[column] = target
            taken.add(target)
        else:
            unmapped.append(column)
    return mapped, unmapped


def detect_entity(columns: list[str], sheet_name: str | None = None) -> str | None:
    """Sheet or JSON key name first; otherwise the one entity whose required columns are all present."""
    key = normalise(sheet_name or "")
    for entity in SCHEMAS:
        if key and (key == entity or key == entity.rstrip("s")):
            return entity
    candidates = []
    for entity in SCHEMAS:
        mapped, _ = map_columns(entity, columns)
        needed = required_fields(entity)
        if needed <= set(mapped.values()) | ({"event_id"} if entity == "logins" else set()):
            candidates.append((len(needed), len(mapped), entity))
    candidates.sort(reverse=True)
    if not candidates or (len(candidates) > 1 and candidates[0][:2] == candidates[1][:2]):
        return None
    return candidates[0][2]
