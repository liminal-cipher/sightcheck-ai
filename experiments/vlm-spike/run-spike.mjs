import assert from 'node:assert/strict';
import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import http from 'node:http';
import * as THREE from 'three';
import {handleApi} from '../../server/api.mjs';
import {VenueViewer} from '../../src/scene.js';
import {adaptBase} from './adapter.mjs';

const root = new URL('../../', import.meta.url);
const sources = {
  baseImage: 'public/engine-plan.png', fixture: 'public/engine-demo.json',
  baseVlm: 'experiments/vlm-spike/fixtures/base-vlm-output.json',
  railingImage: 'experiments/vlm-spike/fixtures/railing-plan.png',
  railingVlm: 'experiments/vlm-spike/fixtures/railing-vlm-output.json',
};
const bytes = Object.fromEntries(await Promise.all(Object.entries(sources).map(async ([key, path]) => [key, await readFile(new URL(path, root))])));
const json = key => JSON.parse(bytes[key].toString('utf8'));
function pngSize(data) {
  assert.equal(data.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
  return {width: data.readUInt32BE(16), height: data.readUInt32BE(20)};
}
const base = json('baseVlm'), fixture = json('fixture'), railing = json('railingVlm');
const input = adaptBase(base, fixture, pngSize(bytes.baseImage));
assert.equal(input.seats.length, 20);
input.seats.forEach((s, i) => {
  assert.equal(s.label, base.seats[i].seat_number);
  assert.deepEqual([s.xPx, s.yPx], [base.seats[i].center_px.x, base.seats[i].center_px.y]);
});
const server = http.createServer((req, res) => {handleApi(req, res).then(handled => {if (!handled) {res.writeHead(404); res.end();}});});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const statuses = {};
async function post(path, data) {
  const reply = await fetch(`http://127.0.0.1:${server.address().port}/api/v1/${path}`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data),
  });
  statuses[path] = reply.status;
  const result = await reply.json();
  assert.equal(reply.status, 200, JSON.stringify(result));
  return result;
}
try {
  const converted = await post('convert', input);
  assert.equal(converted.model.seats.length, 20);
  assert.equal(converted.cameras.length, 20);
  converted.model.seats.forEach(s => assert.ok([s.x, s.floor, s.z].every(Number.isFinite)));
  converted.cameras.forEach((c, i) => {
    const s = converted.model.seats[i];
    assert.equal(c.seatLabel, s.label);
    assert.deepEqual(c.position, [s.x, s.floor + 1.2, s.z]);
    assert.ok(c.target.every(Number.isFinite));
    // Exercise the actual viewer camera method without claiming a WebGL render.
    const camera = new THREE.PerspectiveCamera();
    VenueViewer.prototype.positionCamera.call({model: converted.model, view: {mode: 'seat', eyeHeight: 1.2}, yaw: 0, pitch: 0}, camera, s, 16 / 9);
    assert.deepEqual(camera.position.toArray(), c.position);
    const direction = new THREE.Vector3(...c.target).sub(camera.position).normalize();
    assert.ok(camera.getWorldDirection(new THREE.Vector3()).distanceTo(direction) < 1e-9);
    assert.equal(camera.fov, c.verticalFov);
  });
  const sightline = await post('sightline', {model: converted.model, seatLabel: 'C3', layout: 'theatre', eyeHeightM: 1.2});
  assert.equal(sightline.sampleCount, 325);
  assert.ok(Number.isFinite(sightline.visible));
  assert.equal(railing.seats.length, 20);
  assert.equal(new Set(railing.seats.map(s => s.seat_number)).size, 20);
  assert.ok(railing.seats.every(s => Number.isFinite(s.center_pixel.x) && Number.isFinite(s.center_pixel.y) && /^[A-D]$/.test(s.row) && s.section === null));
  assert.equal(railing.obstacles.length, 1);
  const rail = railing.obstacles[0];
  assert.equal(rail.label, 'BALCONY RAIL');
  assert.equal(rail.type, 'balcony_rail');
  assert.deepEqual(Object.keys(rail).sort(), ['type', 'label', 'area_pixel', 'certainty', 'notes'].sort());
  const result = {
    executedAt: new Date().toISOString(),
    sources: Object.fromEntries(Object.entries(sources).map(([key, path]) => [key, {path, sha256: createHash('sha256').update(bytes[key]).digest('hex')} ])),
    baseImage: pngSize(bytes.baseImage), railingImage: pngSize(bytes.railingImage), httpStatuses: statuses,
    inputSeatCount: input.seats.length, modelSeatCount: converted.model.seats.length, cameraCount: converted.cameras.length,
    viewerCameraMethodsVerified: converted.cameras.length, webglRenderVerified: false,
    calibration: input.calibration, metresPerPixel: converted.report.metresPerPixel,
    c3Seat: converted.model.seats.find(s => s.label === 'C3'), c3Camera: converted.cameras.find(s => s.seatLabel === 'C3'), sightline,
    basePixelsEqualFixture: input.seats.every(s => {const f = fixture.seats.find(f => f.label === s.label); return s.xPx === f.xPx && s.yPx === f.yPx;}) &&
      JSON.stringify(input.calibration.stageLeft) === JSON.stringify(fixture.calibration.stageLeft) && JSON.stringify(input.calibration.stageRight) === JSON.stringify(fixture.calibration.stageRight),
    railing: {seatCount: railing.seats.length, obstacle: rail, converted: false},
  };
  for (const [name, data] of Object.entries({'convert-input.json': input, 'conversion-result.json': converted, 'model.json': converted.model, 'run-results.json': result}))
    await writeFile(new URL(name, import.meta.url), JSON.stringify(data, null, 2) + '\n');
  console.log(JSON.stringify(result, null, 2));
} finally {await new Promise(resolve => server.close(resolve));}
