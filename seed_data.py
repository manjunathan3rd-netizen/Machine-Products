def default_state():
    machines = [
        {"id": "M1", "name": "Laser Cutter A", "type": "cutting", "status": "available"},
        {"id": "M2", "name": "CNC Mill B", "type": "milling", "status": "available"},
        {"id": "M3", "name": "Assembly Line 1", "type": "assembly", "status": "available"},
        {"id": "M4", "name": "Assembly Line 2", "type": "assembly", "status": "available"},
        {"id": "M5", "name": "Paint Booth", "type": "painting", "status": "available"},
    ]
    workers = [
        {"id": "W1", "name": "A. Kumar", "skills": ["cutting", "milling"]},
        {"id": "W2", "name": "S. Reddy", "skills": ["assembly"]},
        {"id": "W3", "name": "P. Nair", "skills": ["assembly", "painting"]},
        {"id": "W4", "name": "J. Rao", "skills": ["milling", "painting"]},
    ]
    materials = [
        {"id": "MT1", "name": "Steel sheet", "stock": 400, "unit": "kg"},
        {"id": "MT2", "name": "Aluminium rod", "stock": 150, "unit": "kg"},
        {"id": "MT3", "name": "Paint (industrial)", "stock": 60, "unit": "L"},
    ]
    orders = [
        {"id": "ORD-01", "customer": "Vantage Auto", "tier": "platinum", "type": "cutting", "qty": 220, "duration": 5, "deadline": 14, "material_id": "MT1", "material_qty": 80},
        {"id": "ORD-02", "customer": "Coastal Metals", "tier": "standard", "type": "milling", "qty": 90, "duration": 6, "deadline": 30, "material_id": "MT2", "material_qty": 40},
        {"id": "ORD-03", "customer": "Orion Devices", "tier": "gold", "type": "assembly", "qty": 150, "duration": 4, "deadline": 18, "material_id": "MT1", "material_qty": 20},
        {"id": "ORD-04", "customer": "Northline Freight", "tier": "silver", "type": "painting", "qty": 60, "duration": 3, "deadline": 22, "material_id": "MT3", "material_qty": 25},
        {"id": "ORD-05", "customer": "Vantage Auto", "tier": "platinum", "type": "assembly", "qty": 300, "duration": 7, "deadline": 20, "material_id": "MT1", "material_qty": 60},
        {"id": "ORD-06", "customer": "Delta Fabrication", "tier": "standard", "type": "cutting", "qty": 70, "duration": 3, "deadline": 40, "material_id": "MT1", "material_qty": 30},
        {"id": "ORD-07", "customer": "Orion Devices", "tier": "gold", "type": "milling", "qty": 130, "duration": 5, "deadline": 26, "material_id": "MT2", "material_qty": 35},
        {"id": "ORD-08", "customer": "Coastal Metals", "tier": "standard", "type": "painting", "qty": 40, "duration": 2, "deadline": 36, "material_id": "MT3", "material_qty": 15},
        {"id": "ORD-09", "customer": "Bramwell Inc", "tier": "silver", "type": "assembly", "qty": 100, "duration": 4, "deadline": 32, "material_id": "MT1", "material_qty": 25},
        {"id": "ORD-10", "customer": "Delta Fabrication", "tier": "standard", "type": "cutting", "qty": 55, "duration": 2, "deadline": 44, "material_id": "MT1", "material_qty": 20},
    ]
    return {"machines": machines, "workers": workers, "materials": materials, "orders": orders}
