document.addEventListener('DOMContentLoaded', () => {
  const addBtn = document.getElementById('addBookBtn');
  const form = document.getElementById('uploadForm');
  const defaultSpreadsInput = document.getElementById('defaultSpreads');
  const productTypeInput = document.getElementById('productType');
  const photoSizeInput = document.getElementById('photoSize'); // value like "10x15" or empty

  // Конфиг размеров (мм) — ключ в 'key' соответствует value в form (например "10x15")
  const sizeConfig = {
    hardcover: {
      cover: (spreads) => ({ width: 430 + Math.max(0, spreads - 2) * 2, height: 305 }),
      spread: { width: 430, height: 305 }
    },
    softcover: {
      cover: { width: 500, height: 350 },
      spread: { width: 430, height: 305 }
    },
    photo: [
      { key: '10x15', w: 102, h: 152, label: '10x15' },
      { key: '13x18', w: 132, h: 182, label: '13x18' },
      { key: '15x20', w: 152, h: 202, label: '15x20' },
      { key: '20x30', w: 203, h: 305, label: '20x30' }
    ]
  };

  // утилита: экранируем имя для вставки в DOM
  function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
  }

  // Создаёт preview thumb и запускает проверку
  function createThumbForFile(file, previewGrid, slotElement) {
    const reader = new FileReader();
    reader.onload = e => {
      const div = document.createElement('div');
      div.className = 'preview-thumb';
      div.innerHTML = `
        <img src="${e.target.result}" alt="">
        <span>${escapeHtml(file.name)}</span>
        <button type="button" class="remove-thumb" title="Удалить">×</button>
        <div class="error-overlay" style="display:none">
          <div class="error-text">Размер не соответствует</div>
          <div class="size-hint"></div>
        </div>
      `;
      previewGrid.appendChild(div);

      // если есть заголовок слота — скрываем его
      const h4 = slotElement ? slotElement.querySelector('h4') : null;
      if (h4) h4.style.display = 'none';

      // удаление файла из input (для multiple — удаляем конкретный файл)
      div.querySelector('.remove-thumb').addEventListener('click', () => {
        removeFileFromInput(file, slotElement, previewGrid, div);
      });

      // проверяем размеры
      checkFileSize(file, slotElement, div);
    };
    reader.readAsDataURL(file);
  }

  // Удаление файла из input.files (работает с multiple)
  function removeFileFromInput(fileToRemove, slotElement, previewGrid, thumbDiv) {
    const input = slotElement.querySelector('input[type="file"]');
    if (!input) return;

    if (input.multiple) {
      const dt = new DataTransfer();
      Array.from(input.files).forEach(f => {
        if (!(f.name === fileToRemove.name && f.size === fileToRemove.size && f.lastModified === fileToRemove.lastModified)) {
          dt.items.add(f);
        }
      });
      input.files = dt.files;
      thumbDiv.remove();
    } else {
      input.value = '';
      previewGrid.innerHTML = '';
      const h4 = slotElement.querySelector('h4');
      if (h4) h4.style.display = '';
      slotElement.classList.add('empty');
    }
  }

  // возвращает { valid: bool, expected: {w,h,label,key} | null }
  function evaluateSize(mmW, mmH, slotElement) {
    const tolerance = 1; // мм
    const productType = (productTypeInput && productTypeInput.value) ? productTypeInput.value : '';
    const spreads = defaultSpreadsInput ? parseInt(defaultSpreadsInput.value || '2') : 2;
    const header = slotElement ? (slotElement.querySelector('h4') ? slotElement.querySelector('h4').textContent.toLowerCase() : '') : '';

    // --- фотопечать ---
    const isPrintSlot = (productType === 'print' || productType === 'photo') || /фото|печать|фотографии|photo/i.test(header) || (slotElement && slotElement.classList.contains('large-slot'));
    if (isPrintSlot) {
      // если явно задан формат (скрытое поле photoSize содержит "10x15" и т.п.)
      const chosen = (photoSizeInput && photoSizeInput.value) ? photoSizeInput.value.trim() : '';
      if (chosen) {
        const target = sizeConfig.photo.find(p => p.key === chosen || p.label === chosen);
        if (target) {
          const ok = comparePhoto(mmW, mmH, target, tolerance);
          return { valid: ok, expected: target };
        }
      }
      // иначе смотрим на ближайший форм-фактор
      let best = null; let bestDiff = Infinity;
      for (const dim of sizeConfig.photo) {
        const diff1 = Math.abs(dim.w - mmW) + Math.abs(dim.h - mmH);
        const diff2 = Math.abs(dim.w - mmH) + Math.abs(dim.h - mmW);
        const diff = Math.min(diff1, diff2);
        if (diff < bestDiff) { bestDiff = diff; best = dim; }
        if (diff1 <= tolerance || diff2 <= tolerance) return { valid: true, expected: dim };
      }
      return { valid: false, expected: best };
    }

    // --- фотокниги (cover/spread/page) ---
    const input = slotElement ? slotElement.querySelector('input[type="file"]') : null;
    const id = input ? input.id : '';
    const isCover = /-cover-/.test(id) || /обложка/.test(header);
    const isSpread = /-spread-/.test(id) || /разворот/.test(header) || /page/.test(header);

    if (productType === 'soft') {
      if (isCover) {
        const exp = sizeConfig.softcover.cover;
        return { valid: compareSize(mmW, mmH, exp, tolerance), expected: exp };
      } else if (isSpread) {
        const exp = sizeConfig.softcover.spread;
        return { valid: compareSize(mmW, mmH, exp, tolerance), expected: exp };
      }
    } else {
      if (isCover) {
        const exp = sizeConfig.hardcover.cover(spreads || 2);
        return { valid: compareSize(mmW, mmH, exp, tolerance), expected: exp };
      } else if (isSpread) {
        const exp = sizeConfig.hardcover.spread;
        return { valid: compareSize(mmW, mmH, exp, tolerance), expected: exp };
      }
    }

    return { valid: true, expected: null };
  }

  function compareSize(mmW, mmH, exp, tol) {
    return (Math.abs(exp.width - mmW) <= tol && Math.abs(exp.height - mmH) <= tol) ||
           (Math.abs(exp.width - mmH) <= tol && Math.abs(exp.height - mmW) <= tol);
  }

  function comparePhoto(mmW, mmH, dim, tol) {
    return (Math.abs(dim.w - mmW) <= tol && Math.abs(dim.h - mmH) <= tol) ||
           (Math.abs(dim.w - mmH) <= tol && Math.abs(dim.h - mmW) <= tol);
  }

  // Чтение размеров изображения и DPI/EXIF попытка (если есть) — возвращаем размеры в мм
  function readImageMm(file, callback) {
    const img = new Image();
    img.onload = function() {
      const pxW = img.width, pxH = img.height;

      // Попробуем прочитать DPI из заголовка JFIF (упрощённо), если нет — используем 300dpi
      const reader = new FileReader();
      reader.onload = function(e) {
        const buffer = e.target.result;
        let dpiX = 300, dpiY = 300; // default
        try {
          const bytes = new Uint8Array(buffer);
          // простой поиск "JFIF" (не надёжно, но лучше, чем ничего)
          const ascii = Array.from(bytes).map(b => String.fromCharCode(b)).join('');
          const jfifIndex = ascii.indexOf('JFIF');
          if (jfifIndex !== -1) {
            // попытка парсинга значения — не гарантируется везде
            const unit = bytes[jfifIndex + 7];
            const xD = bytes[jfifIndex + 8];
            const yD = bytes[jfifIndex + 9];
            if (unit === 1 && xD && yD) { dpiX = xD; dpiY = yD; }
            else if (unit === 2 && xD && yD) { dpiX = xD * 2.54; dpiY = yD * 2.54; }
          }
        } catch (err) {
          // молча используем 300dpi
        }
        const mmW = +(pxW / dpiX * 25.4).toFixed(2);
        const mmH = +(pxH / dpiY * 25.4).toFixed(2);
        callback(mmW, mmH);
      };
      reader.readAsArrayBuffer(file);
    };
    img.onerror = function() { callback(null, null); };
    img.src = URL.createObjectURL(file);
  }

  // Проверяем файл, если не валиден — показываем overlay с expected
  function checkFileSize(file, slotElement, thumbDiv) {
    readImageMm(file, (mmW, mmH) => {
      if (mmW == null || mmH == null) {
        markInvalidThumb(thumbDiv, null);
        return;
      }
      const evalRes = evaluateSize(mmW, mmH, slotElement);
      if (!evalRes.valid) markInvalidThumb(thumbDiv, evalRes.expected);
    });
  }

  function markInvalidThumb(thumbDiv, expected) {
    thumbDiv.classList.add('invalid');
    const overlay = thumbDiv.querySelector('.error-overlay');
    if (!overlay) return;
    const hint = overlay.querySelector('.size-hint');
    if (expected) {
      if (expected.w && expected.h) hint.textContent = `Ожидаемый размер: ${expected.w}×${expected.h} мм`;
      else if (expected.width && expected.height) hint.textContent = `Ожидаемый размер: ${expected.width}×${expected.height} мм`;
      else hint.textContent = `Ожидаемый размер: неизвестен`;
    } else {
      hint.textContent = `Ожидаемый размер: неизвестен`;
    }
    overlay.style.display = 'flex';
    // белый текст
    const et = overlay.querySelector('.error-text');
    if (et) et.style.color = '#fff';
    hint.style.color = '#fff';
  }

  // Присоединяем обработчики к input-ам
  function attachInput(input) {
    const previewId = input.id.replace('file-', 'preview-');
    // ensure element exists
    const previewGrid = document.getElementById(previewId);
    const slotElement = input.closest('.slot-item');

    // make label clickable even though input is opacity 0
    const label = slotElement ? slotElement.querySelector('.upload-drop-label') : null;
    if (label) label.addEventListener('click', () => input.click());

    input.addEventListener('change', () => {
      const grid = previewGrid;
      if (!grid) return;
      if (!input.multiple) grid.innerHTML = '';
      if (input.files && input.files.length) {
        Array.from(input.files).forEach(file => createThumbForFile(file, grid, slotElement || input.parentElement));
        if (slotElement) slotElement.classList.remove('empty');
      } else {
        if (!input.multiple) grid.innerHTML = '';
        if (slotElement) {
          slotElement.classList.add('empty');
          const h4 = slotElement.querySelector('h4');
          if (h4) h4.style.display = '';
        }
      }
    });
  }

  // Инициализация всех существующих file-input
  document.querySelectorAll('.file-input').forEach(attachInput);

  // Добавление книги (для non-print)
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      const books = document.querySelectorAll('.book-card');
      const newIndex = books.length + 1;
      let spreadsCount = 2;
      const firstBook = books[0];
      if (firstBook) spreadsCount = Math.max(2, firstBook.querySelectorAll('.slot-item').length - 1);

      const newBook = document.createElement('div');
      newBook.classList.add('book-card');
      newBook.setAttribute('data-book', newIndex);

      let slotsHtml = `<div class="slot-item">
          <h4>Обложка</h4>
          <input type="file" id="file-${newIndex}-cover-0" name="file-book-${newIndex}-cover-0" accept="image/*" class="file-input">
          <div class="preview-grid" id="preview-${newIndex}-cover-0"></div>
        </div>`;
      for (let i = 1; i <= spreadsCount; i++) {
        slotsHtml += `<div class="slot-item">
            <h4>Разворот ${i}</h4>
            <input type="file" id="file-${newIndex}-spread-${i}" name="file-book-${newIndex}-spread-${i}" accept="image/*" class="file-input">
            <div class="preview-grid" id="preview-${newIndex}-spread-${i}"></div>
          </div>`;
      }

      newBook.innerHTML = `<div class="book-header">
          <h3>Книга ${newIndex}</h3>
          <button type="button" class="delete-book">Удалить</button>
        </div>
        <div class="slots">${slotsHtml}</div>`;

      form.insertBefore(newBook, form.querySelector('.actions'));
      newBook.querySelectorAll('.file-input').forEach(attachInput);
      const delBtn = newBook.querySelector('.delete-book');
      if (delBtn) attachDeleteHandler(delBtn);
    });
  }

  function attachDeleteHandler(btn) {
    btn.addEventListener('click', () => {
      const card = btn.closest('.book-card');
      if (!card) return;
      card.remove();
      updateBookNumbers();
    });
  }

  function updateBookNumbers() {
    const books = document.querySelectorAll('.book-card');
    books.forEach((book, idx) => {
      const index = idx + 1;
      book.setAttribute('data-book', index);
      const h3 = book.querySelector('h3');
      if (h3) h3.textContent = `Книга ${index}`;
      book.querySelectorAll('.file-input').forEach((input) => {
        const parts = input.id.split('-');
        const slotType = parts[2] || 'photo';
        const slotIndex = parts[3] || '0';
        input.id = `file-${index}-${slotType}-${slotIndex}`;
        input.name = `file-book-${index}-${slotType}-${slotIndex}`;
        const preview = input.closest('.slot-item') ? input.closest('.slot-item').querySelector('.preview-grid') : null;
        if (preview) preview.id = `preview-${index}-${slotType}-${slotIndex}`;
        if (input) input.dataset.preview = preview ? preview.id : '';
      });
    });
  }

  document.querySelectorAll('.delete-book').forEach(attachDeleteHandler);
});
