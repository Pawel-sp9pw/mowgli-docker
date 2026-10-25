from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1))


def replace_between(path: Path, start: str, end: str, new: str) -> None:
    text = path.read_text()
    start_pos = text.find(start)
    if start_pos < 0:
        raise RuntimeError(f"start marker not found in {path}: {start!r}")
    end_pos = text.find(end, start_pos)
    if end_pos < 0:
        raise RuntimeError(f"end marker not found in {path}: {end!r}")
    path.write_text(text[:start_pos] + new + "\n\n" + text[end_pos:])


openmower = Path("/src/pkg/api/openmower.go")
map_area = Path("/src/pkg/msgs/mower_map/MapArea.go")

# The v2 frontend/runtime must be paired with the v2 backend.  Extend its
# generated mower_map schema to the current Jeremy/OpenMower MapArea layout.
replace_once(
    openmower,
    '\t"log"\n\t"net/http"',
    '\t"log"\n\t"math"\n\t"net/http"',
)

replace_once(
    openmower,
    '\tPublisherRoute(group, provider)\n}\n\n',
    '''\tPublisherRoute(group, provider)\n}\n\n// normalizeLegacyMapArea fills fields which were added to mower_map/MapArea\n// after this GUI's messages were generated. The editor does not expose all of\n// these settings, so use the current OpenMower defaults.\nfunc normalizeLegacyMapArea(area *mower_map.MapArea) {\n\tarea.Active = true\n\tarea.Angle = math.NaN()\n\tarea.OutlineCount = -1\n\tarea.OutlineOverlapCount = -1\n\tarea.OutlineOffset = math.NaN()\n}\n\n''',
)

replace_once(
    openmower,
    '''\t\tif err != nil {\n\t\t\treturn\n\t\t}\n\t\terr = provider.CallService(c.Request.Context(), "/mower_map_service/add_mowing_area", &mower_map.AddMowingAreaSrv{}, &CallReq, &mower_map.AddMowingAreaSrvRes{})''',
    '''\t\tif err != nil {\n\t\t\treturn\n\t\t}\n\t\tnormalizeLegacyMapArea(&CallReq.Area)\n\t\terr = provider.CallService(c.Request.Context(), "/mower_map_service/add_mowing_area", &mower_map.AddMowingAreaSrv{}, &CallReq, &mower_map.AddMowingAreaSrvRes{})''',
)

new_replace_route = '''func ReplaceMapRoute(group *gin.RouterGroup, provider types.IRosProvider) {\n\tgroup.PUT("/map", func(c *gin.Context) {\n\t\t// Decode and validate the whole replacement BEFORE clear_map.  The old\n\t\t// route cleared and persisted an empty map first, so a decode/service\n\t\t// mismatch could destroy map.json.\n\t\tvar CallReq mower_map.ReplaceMowingAreaSrvReq\n\t\terr := unmarshalROSMessage[*mower_map.ReplaceMowingAreaSrvReq](c.Request.Body, &CallReq)\n\t\tif err != nil {\n\t\t\tc.JSON(http.StatusBadRequest, ErrorResponse{Error: err.Error()})\n\t\t\treturn\n\t\t}\n\t\tif len(CallReq.Areas) == 0 {\n\t\t\tc.JSON(http.StatusBadRequest, ErrorResponse{Error: "refusing to replace map with an empty area list; use DELETE /openmower/map to clear intentionally"})\n\t\t\treturn\n\t\t}\n\n\t\tfor i := range CallReq.Areas {\n\t\t\tnormalizeLegacyMapArea(&CallReq.Areas[i].Area)\n\t\t}\n\n\t\terr = provider.CallService(c.Request.Context(), "/mower_map_service/clear_map", &mower_map.ClearMapSrv{}, &mower_map.ClearMapSrvReq{}, &mower_map.ClearMapSrvRes{})\n\t\tif err != nil {\n\t\t\tc.JSON(500, ErrorResponse{Error: err.Error()})\n\t\t\treturn\n\t\t}\n\n\t\tfor _, element := range CallReq.Areas {\n\t\t\terr = provider.CallService(c.Request.Context(), "/mower_map_service/add_mowing_area", &mower_map.AddMowingAreaSrv{}, &element, &mower_map.AddMowingAreaSrvRes{})\n\t\t\tif err != nil {\n\t\t\t\tc.JSON(500, ErrorResponse{Error: err.Error()})\n\t\t\t\treturn\n\t\t\t}\n\t\t}\n\n\t\tc.JSON(200, OkResponse{})\n\t})\n}'''

replace_between(
    openmower,
    "func ReplaceMapRoute(group *gin.RouterGroup, provider types.IRosProvider) {",
    "// SetDockingPointRoute set the docking point",
    new_replace_route,
)

replace_once(
    map_area,
    '''type MapArea struct {\n    msg.Package `ros:"mower_map"`\n    Name string\n    Area geometry_msgs.Polygon\n    Obstacles []geometry_msgs.Polygon\n}\n''',
    '''type MapArea struct {\n    msg.Package `ros:"mower_map"`\n    Name string\n    Active bool\n    Area geometry_msgs.Polygon\n    Obstacles []geometry_msgs.Polygon\n    Angle float64\n    OutlineCount int32 `rosname:"outline_count"`\n    OutlineOverlapCount int32 `rosname:"outline_overlap_count"`\n    OutlineOffset float64 `rosname:"outline_offset"`\n}\n''',
)

# Mow Area previously called /mower_service/start_in_area, which the
# deployed OpenMower backend does not implement. Send a validated selection
# to the Mowgli mower_logic area-start subscriber instead.
replace_once(
    openmower,
    '"github.com/bluenviron/goroslib/v2/pkg/msgs/geometry_msgs"',
    '"github.com/bluenviron/goroslib/v2/pkg/msgs/geometry_msgs"\n'
    '\\t"github.com/bluenviron/goroslib/v2/pkg/msgs/std_msgs"',
)
replace_once(
    openmower,
    '''\t\tcase "start_in_area":
\t\t\tvar CallReq mower_msgs.StartInAreaSrvReq
\t\t\terr = c.BindJSON(&CallReq)
\t\t\tif err != nil {
\t\t\t\treturn
\t\t\t}
\t\t\terr = provider.CallService(c.Request.Context(), "/mower_service/start_in_area", &mower_msgs.StartInAreaSrv{}, &CallReq, &mower_msgs.StartInAreaSrvRes{})''',
    '''\t\tcase "start_in_area":
\t\t\tvar request struct {
\t\t\t\tArea *uint8 `json:"area"`
\t\t\t}
\t\t\tif err = c.ShouldBindJSON(&request); err != nil || request.Area == nil {
\t\t\t\tc.JSON(http.StatusBadRequest, ErrorResponse{Error: "missing or invalid area index"})
\t\t\t\treturn
\t\t\t}
\t\t\tpublisher, publishErr := provider.Publisher("/mowgli/start_in_area", &std_msgs.UInt8{})
\t\t\tif publishErr != nil {
\t\t\t\tc.JSON(http.StatusServiceUnavailable, ErrorResponse{Error: publishErr.Error()})
\t\t\t\treturn
\t\t\t}
\t\t\tdefer publisher.Close()
\t\t\t// Wait for the ROS TCPROS handshake before the one-shot command.
\t\t\ttime.Sleep(500 * time.Millisecond)
\t\t\tpublisher.Write(&std_msgs.UInt8{Data: *request.Area})''',
)

print("OpenMower GUI v2 map compatibility changes applied successfully")
