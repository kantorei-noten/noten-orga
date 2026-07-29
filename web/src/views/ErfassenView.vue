<script setup>
import { onMounted, ref } from 'vue'

import { api } from '@/api'

const form = ref({
  titel: '', komponist: '', textdichter: '', gattung: '',
  besetzung: '', tonart: '', schwierigkeit: null, anlass_id: '',
  gl: '', eg: '', tags: ''
})
const komponisten = ref([])
const tagVorschlaege = ref([])
const besetzungen = ref([])
const anlaesse = ref([])
const dubletten = ref([])
const fehler = ref('')
const busy = ref(false)
const erstellt = ref(null)
const datei = ref(null)
const uploadBusy = ref(false)

onMounted(async () => {
  besetzungen.value = await api.get('/besetzungen')
  anlaesse.value = await api.get('/anlaesse')
  tagVorschlaege.value = await api.get('/tags')
})

async function komponistTippen() {
  const q = form.value.komponist.trim()
  komponisten.value = q ? await api.get('/komponisten?q=' + encodeURIComponent(q)) : []
}

async function pruefeDubletten() {
  const t = form.value.titel.trim()
  dubletten.value = t.length >= 3 ? await api.get('/werke/aehnlich?titel=' + encodeURIComponent(t)) : []
}

function splitNums(cell, buch) {
  return (cell || '').split(/[;,]/).map((s) => s.trim()).filter(Boolean).map((n) => ({ buch, nummer: n }))
}

async function speichern() {
  fehler.value = ''
  busy.value = true
  try {
    const payload = {
      titel: form.value.titel,
      komponist: form.value.komponist || null,
      textdichter: form.value.textdichter || null,
      gattung: form.value.gattung || null,
      besetzung: form.value.besetzung || null,
      tonart: form.value.tonart || null,
      schwierigkeit: form.value.schwierigkeit ? Number(form.value.schwierigkeit) : null,
      anlass_ids: form.value.anlass_id ? [form.value.anlass_id] : [],
      gesangbuch: [...splitNums(form.value.gl, 'GL'), ...splitNums(form.value.eg, 'EG')],
      tags: form.value.tags.split(',').map((s) => s.trim()).filter(Boolean)
    }
    erstellt.value = await api.post('/werke', payload)
  } catch (e) {
    fehler.value = 'Speichern fehlgeschlagen: ' + e.message
  } finally {
    busy.value = false
  }
}

async function hochladen(ev) {
  const file = ev.target.files[0]
  if (!file || !erstellt.value) return
  uploadBusy.value = true
  fehler.value = ''
  try {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('ausgabe_id', erstellt.value.ausgaben[0].id)
    fd.append('art', 'scan_pdf')
    datei.value = await api.upload('/dateien', fd)
  } catch (e) {
    fehler.value = 'Upload fehlgeschlagen: ' + e.message
  } finally {
    uploadBusy.value = false
  }
}
</script>

<template>
  <h1>Werk erfassen</h1>

  <div v-if="!erstellt" class="card" style="max-width: 640px">
    <label class="field"><span>Titel *</span>
      <input class="input" v-model="form.titel" @blur="pruefeDubletten" />
    </label>

    <div v-if="dubletten.length" class="dub">
      <b>Mögliche Dublette{{ dubletten.length > 1 ? 'n' : '' }}:</b>
      <RouterLink
        v-for="d in dubletten"
        :key="d.id"
        :to="{ name: 'werk', params: { id: d.id } }"
        class="dub-item"
      >{{ d.titel }}<span class="muted"> · {{ d.aehnlichkeit }}</span></RouterLink>
    </div>

    <div class="grid2">
      <label class="field"><span>Komponist</span>
        <input class="input" v-model="form.komponist" list="komp-list" @input="komponistTippen" />
        <datalist id="komp-list"><option v-for="k in komponisten" :key="k" :value="k" /></datalist>
      </label>
      <label class="field"><span>Textdichter</span>
        <input class="input" v-model="form.textdichter" />
      </label>
      <label class="field"><span>Gattung</span>
        <input class="input" v-model="form.gattung" placeholder="Choral, Motette …" />
      </label>
      <label class="field"><span>Besetzung</span>
        <select class="input" v-model="form.besetzung">
          <option value="">—</option>
          <option v-for="b in besetzungen" :key="b.kuerzel" :value="b.kuerzel">{{ b.name }}</option>
        </select>
      </label>
      <label class="field"><span>Tonart</span>
        <input class="input" v-model="form.tonart" placeholder="z. B. D-Dur" />
      </label>
      <label class="field"><span>Schwierigkeit (1–5)</span>
        <input class="input" type="number" min="1" max="5" v-model="form.schwierigkeit" />
      </label>
      <label class="field"><span>Gotteslob-Nr. (GL)</span>
        <input class="input" v-model="form.gl" placeholder="z. B. 405" />
      </label>
      <label class="field"><span>Ev. Gesangbuch (EG)</span>
        <input class="input" v-model="form.eg" placeholder="z. B. 321" />
      </label>
      <label class="field"><span>Anlass / Kirchenjahr</span>
        <select class="input" v-model="form.anlass_id">
          <option value="">—</option>
          <option v-for="a in anlaesse" :key="a.id" :value="a.id">{{ a.name }}</option>
        </select>
      </label>
      <label class="field"><span>Tags (Komma-getrennt)</span>
        <input class="input" v-model="form.tags" list="tag-list" />
        <datalist id="tag-list"><option v-for="t in tagVorschlaege" :key="t" :value="t" /></datalist>
      </label>
    </div>

    <p v-if="fehler" class="error">{{ fehler }}</p>
    <button class="btn primary" :disabled="busy || !form.titel.trim()" @click="speichern">
      {{ busy ? 'Speichern …' : 'Werk anlegen' }}
    </button>
  </div>

  <div v-else class="card" style="max-width: 640px">
    <p><span class="badge ok">angelegt</span> <b>{{ erstellt.titel }}</b></p>
    <label class="field"><span>Scan/PDF hochladen (optional)</span>
      <input class="input" type="file" accept="application/pdf,.musicxml,.mxl,.xml" @change="hochladen" :disabled="uploadBusy" />
    </label>
    <p v-if="uploadBusy" class="muted">Lädt hoch …</p>
    <div v-if="datei" class="upload-ok">
      <img v-if="datei.hat_vorschau" :src="`/api/dateien/${datei.id}/thumbnail`" alt="Vorschau" class="thumb" />
      <div>{{ datei.seiten }} Seite(n) · {{ datei.mime }}</div>
    </div>
    <p v-if="fehler" class="error">{{ fehler }}</p>
    <div class="toolbar" style="margin-top: 12px">
      <RouterLink class="btn secondary" :to="{ name: 'werk', params: { id: erstellt.id } }">Zum Werk</RouterLink>
      <RouterLink class="btn ghost" to="/erfassen" @click="erstellt = null">Nächstes erfassen</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
@media (max-width: 560px) { .grid2 { grid-template-columns: 1fr; } }
.dub { background: var(--warning-tint); color: var(--warning); border-radius: var(--radius-sm); padding: 10px 12px; margin-bottom: 14px; font-size: var(--text-sm); }
.dub-item { display: block; color: var(--warning); margin-top: 4px; }
.upload-ok { display: flex; align-items: center; gap: 14px; margin: 8px 0; }
.thumb { width: 80px; height: auto; border: 1px solid var(--border); border-radius: 4px; }
</style>
