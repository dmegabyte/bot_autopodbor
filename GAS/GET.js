function doGet(e) { return processData(e.parameter); }
function doPost(e) {
  var data = {};
  try { data = JSON.parse(e.postData.contents); } 
  catch (err) { data = e.parameter; }
  return processData(data);
}

function normalizePhone(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") {
    return Math.round(value).toString();
  }
  return String(value)
    .replace(/[^\d+]/g, "")
    .replace(/^\+/, "");
}

function processData(data) {
  var lock = LockService.getScriptLock();
  lock.tryLock(10000);

  try {
    // --- ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ ---
    // Мы вернем это в ответе, чтобы вы видели, что пришло
    var debugReceived = JSON.stringify(data);

    var phoneRaw = data.phone || data.phone_number || data.mobile;
    var phone = normalizePhone(phoneRaw);
    var tgUserId = data.tg_user_id || data.user_id;

    // Require either phone or tg_user_id for identification
    if (!phone && !tgUserId) {
      return responseJSON({ "status": "error", "message": "No phone or tg_user_id" });
    }

    // КАРТА ПОЛЕЙ
    var fieldMap = {
      "phone_number": ["phone", "phone_number", "mobile"],
      "timestamp": ["timestamp"],
      "brand": ["brand", "marka"],
      "model": ["model"],
      "year": ["year", "god"],
      "city": ["city", "gorod", "location"],
      "budget": ["budget", "price"],
      "manager": ["manager", "manager_consent", "consent", "soglasie"],
      "client_name": ["client_name", "name"],
      "tg_user_id": ["tg_user_id", "user_id"],
      "tg_username": ["tg_username", "username"],
      "tag": ["tag", "source", "utm"]
    };

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getActiveSheet();
    var timestamp = new Date();

    // ЗАГОЛОВКИ
    var headers = [];
    if (sheet.getLastColumn() > 0) {
      headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    }

    var colIndexes = {};
    for (var key in fieldMap) {
      var colIndex = headers.indexOf(key);
      if (colIndex === -1) {
        colIndex = headers.length;
        sheet.getRange(1, colIndex + 1).setValue(key);
        headers.push(key);
      }
      colIndexes[key] = colIndex;
      if (key === "phone_number") {
        var rowsToFormat = Math.max(sheet.getMaxRows() - 1, 1);
        sheet.getRange(2, colIndex + 1, rowsToFormat, 1).setNumberFormat("@");
      }
    }

    // ПОИСК: Priority 1 - by phone, Priority 2 - by tg_user_id
    var rowIndex = -1;
    var phoneColIndex = colIndexes["phone_number"];
    var tgUserIdColIndex = colIndexes["tg_user_id"];
    var lastRow = sheet.getLastRow();

    if (lastRow > 1) {
      var allData = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();

      for (var i = 0; i < allData.length; i++) {
        // Priority 1: Search by phone (if phone provided)
        if (phone) {
          var cellValue = allData[i][phoneColIndex];
          var normalizedCell = normalizePhone(cellValue);
          if (normalizedCell === phone) {
            rowIndex = i + 2;
            break;
          }
        }
        // Priority 2: Search by tg_user_id (if phone not provided)
        else if (tgUserId) {
          var cellTgId = String(allData[i][tgUserIdColIndex]);
          if (cellTgId === String(tgUserId)) {
            rowIndex = i + 2;
            break;
          }
        }
      }
    }
    Logger.log("Search phone: " + phone + ", tg_user_id: " + tgUserId + ", found at row: " + rowIndex);

    // ЗАПИСЬ
    var action = "";
    if (rowIndex !== -1) {
      action = "updated";
      for (var key in fieldMap) {
        // Update phone_number if provided (allows transition from tg_user_id to phone)
        if (key === "phone_number") {
          if (phone) sheet.getRange(rowIndex, colIndexes[key] + 1).setValue(phone);
          continue;
        }
        var val = null;
        if (key === "timestamp") val = timestamp;
        else {
          var keys = fieldMap[key];
          for (var k = 0; k < keys.length; k++) {
            // Проверка: если ключ есть в данных
            if (data[keys[k]] !== undefined) {
              val = data[keys[k]];
              break;
            }
          }
        }
        if (val !== null) sheet.getRange(rowIndex, colIndexes[key] + 1).setValue(val);
      }
    } else {
      action = "created";
      var newRow = new Array(headers.length).fill("");
      for (var key in fieldMap) {
        var val = "";
        if (key === "phone_number") val = phone;
        else if (key === "timestamp") val = timestamp;
        else {
          var keys = fieldMap[key];
          for (var k = 0; k < keys.length; k++) {
            if (data[keys[k]] !== undefined) {
              val = data[keys[k]];
              break;
            }
          }
        }
        newRow[colIndexes[key]] = val;
      }
      sheet.appendRow(newRow);
      var appendedRow = sheet.getLastRow();
      // Format phone column as text and set value (may be empty on first sync)
      var phoneCell = sheet.getRange(appendedRow, colIndexes["phone_number"] + 1);
      phoneCell.setNumberFormat("@");
      if (phone) phoneCell.setValue(phone);
    }

    // Извлечь city и client_name для диагностики
    var extractedCity = null;
    var cityKeys = ["city", "gorod", "location"];
    for (var i = 0; i < cityKeys.length; i++) {
      if (data[cityKeys[i]] !== undefined) {
        extractedCity = data[cityKeys[i]];
        break;
      }
    }

    var extractedName = null;
    var nameKeys = ["client_name", "name"];
    for (var i = 0; i < nameKeys.length; i++) {
      if (data[nameKeys[i]] !== undefined) {
        extractedName = data[nameKeys[i]];
        break;
      }
    }

    // В ответе возвращаем debug_data с детальной информацией о city и client_name
    return responseJSON({
      "status": "success",
      "action": action,
      "phone": phone,
      "debug_received_data": data,
      "debug_extracted": {
        "city": extractedCity,
        "client_name": extractedName
      },
      "debug_col_indexes": {
        "city": colIndexes["city"],
        "client_name": colIndexes["client_name"]
      }
    });

  } catch (e) {
    return responseJSON({ "status": "error", "message": e.toString() });
  } finally {
    lock.releaseLock();
  }
}

function responseJSON(content) {
  return ContentService.createTextOutput(JSON.stringify(content)).setMimeType(ContentService.MimeType.JSON);
}
