import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {adaptBase} from './adapter.mjs';
import {convertPlan} from '../../src/conversion.js';
const read = async path => JSON.parse(await readFile(new URL(path, import.meta.url), 'utf8'));
const base = await read('fixtures/base-vlm-output.json');
const fixture = await read('../../public/engine-demo.json');
const convert = (v = base, f = fixture) => convertPlan(adaptBase(v, f, fixture.image));

test('fixture pixel/row mutations are ignored; measurement lookup is by label', () => {
  const changed = structuredClone(fixture);
  changed.seats.reverse().forEach(s => {s.xPx = -999; s.yPx = -999; s.row = 99;});
  changed.calibration.stageLeft = [-999, -999]; changed.calibration.stageRight = [-999, -999];
  assert.deepEqual(convert(base, changed), convert());
});
test('VLM seat pixels, stage region and row drive the actual engine output', () => {
  const before = convert();
  const moved = structuredClone(base); moved.seats[12].center_px.x += 60;
  const after = convert(moved);
  assert.ok(Math.abs(after.model.seats[12].x - before.model.seats[12].x - 1) < 1e-9);
  assert.ok(Math.abs(after.cameras[12].position[0] - before.cameras[12].position[0] - 1) < 1e-9);
  const stage = structuredClone(base); stage.stage.region_px.y_max += 60;
  assert.ok(Math.abs(convert(stage).model.seats[12].z - before.model.seats[12].z + 1) < 1e-9);
  assert.deepEqual(adaptBase(base, fixture, fixture.image).seats.map(s => s.row), base.seats.map(s => 'ABCD'.indexOf(s.row)));
});
test('VLM metric/obstacle additions are ignored; missing human measurements fail', () => {
  const untrusted = structuredClone(base);
  untrusted.seats[12].floorM = 12; untrusted.seats[12].section = 'AI guess';
  untrusted.stage.depthM = 18; untrusted.obstacles = [{position: [1, 2, 3]}];
  assert.deepEqual(convert(untrusted), convert());
  const missing = structuredClone(fixture); delete missing.seats[12].floorM;
  assert.throws(() => convert(base, missing), /floorM/);
  const unmatched = structuredClone(base); unmatched.seats[12].seat_number = 'C99';
  assert.throws(() => convert(unmatched), /Missing measurement/);
});
test('railing schema and different image dimensions cannot enter this adapter', async () => {
  const rail = await read('fixtures/railing-vlm-output.json');
  assert.throws(() => adaptBase(rail, fixture, {width: 1254, height: 1254}), /dimensions/);
  assert.throws(() => adaptBase(rail, fixture, fixture.image), /region_px/);
});
