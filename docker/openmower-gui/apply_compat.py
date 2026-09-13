from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1))


openmower = Path("/src/pkg/api/openmower.go")
map_area = Path("/src/pkg/msgs/mower_map/MapArea.go")

replace_once(
    openmower,
    '\t"log"\n\t"net/http"',
    '\t"log"\n\t"math"\n\t"net/http"',
)

replace_once(
    openmower,
    '\tPublisherRoute(group, provider)\n}\n\n',
    '''\tPublisherRoute(group, provider)\n}\n\n// normalizeLegacyMapArea fills fields which were added to mower_map/MapArea\n// after this GUI was originally generated. The legacy editor does not expose\n// these settings, so preserve the current OpenMower defaults.\nfunc normalizeLegacyMapArea(area *mower_map.MapArea) {\n\tarea.Active = true\n\tarea.Angle = math.NaN()\n\tarea.OutlineCount = -1\n\tarea.OutlineOverlapCount = -1\n\tarea.OutlineOffset = math.NaN()\n}\n\n''',
)

replace_once(
    openmower,
    '''\t\tif err != nil {\n\t\t\treturn\n\t\t}\n\t\terr = provider.CallService(c.Request.Context(), "/mower_map_service/add_mowing_area", &mower_map.AddMowingAreaSrv{}, &CallReq, &mower_map.AddMowingAreaSrvRes{})''',
    '''\t\tif err != nil {\n\t\t\treturn\n\t\t}\n\t\tnormalizeLegacyMapArea(&CallReq.Area)\n\t\terr = provider.CallService(c.Request.Context(), "/mower_map_service/add_mowing_area", &mower_map.AddMowingAreaSrv{}, &CallReq, &mower_map.AddMowingAreaSrvRes{})''',
)

old_replace_route = '''func ReplaceMapRoute(group *gin.RouterGroup, provider types.IRosProvider) {\n\tgroup.PUT("/map", func(c *gin.Context) {\n\t\terr := provider.CallService(c.Request.Context(), "/mower_map_service/clear_map", &mower_map.ClearMapSrv{}, &mower_map.ClearMapSrvReq{}, &mower_map.ClearMapSrvRes{})\n\t\tif err != nil {\n\t\t\tc.JSON(500, ErrorResponse{Error: err.Error()})\n\t\t\treturn\n\t\t} else {\n\t\t\tvar CallReq mower_map.ReplaceMowingAreaSrvReq\n\t\t\terr := unmarshalROSMessage[*mower_map.ReplaceMowingAreaSrvReq](c.Request.Body, &CallReq)\n\t\t\tif err != nil {\n\t\t\t\tc.JSON(500, ErrorResponse{Error: err.Error()})\n\t\t\t\treturn\n\t\t\t}\n\t\t\tfor _, element := range CallReq.Areas {\n\t\t\t\terr = provider.CallService(c.Request.Context(), "/mower_map_service/add_mowing_area", &mower_map.AddMowingAreaSrv{}, &element, &mower_map.AddMowingAreaSrvRes{})\n\t\t\t\tif err != nil {\n\t\t\t\t\tc.JSON(500, ErrorResponse{Error: err.Error()})\n\t\t\t\t\treturn\n\t\t\t\t}\n\t\t\t}\n\n\t\t\tc.JSON(200, OkResponse{})\n\t\t}\n\t})\n}\n'''

new_replace_route = '''func ReplaceMapRoute(group *gin.RouterGroup, provider types.IRosProvider) {\n\tgroup.PUT("/map", func(c *gin.Context) {\n\t\t// Parse and validate the complete request BEFORE touching the persisted map.\n\t\t// Previously clear_map was called first, so any decode/service mismatch left\n\t\t// map.json empty and forced a manual restore.\n\t\tvar CallReq mower_map.ReplaceMowingAreaSrvReq\n\t\terr := unmarshalROSMessage[*mower_map.ReplaceMowingAreaSrvReq](c.Request.Body, &CallReq)\n\t\tif err != nil {\n\t\t\tc.JSON(http.StatusBadRequest, ErrorResponse{Error: err.Error()})\n\t\t\treturn\n\t\t}\n\t\tif len(CallReq.Areas) == 0 {\n\t\t\tc.JSON(http.StatusBadRequest, ErrorResponse{Error: "refusing to replace map with an empty area list; use DELETE /openmower/map to clear intentionally"})\n\t\t\treturn\n\t\t}\n\t\tfor i := range CallReq.Areas {\n\t\t\tnormalizeLegacyMapArea(&CallReq.Areas[i].Area)\n\t\t}\n\n\t\terr = provider.CallService(c.Request.Context(), "/mower_map_service/clear_map", &mower_map.ClearMapSrv{}, &mower_map.ClearMapSrvReq{}, &mower_map.ClearMapSrvRes{})\n\t\tif err != nil {\n\t\t\tc.JSON(500, ErrorResponse{Error: err.Error()})\n\t\t\treturn\n\t\t}\n\n\t\tfor _, element := range CallReq.Areas {\n\t\t\terr = provider.CallService(c.Request.Context(), "/mower_map_service/add_mowing_area", &mower_map.AddMowingAreaSrv{}, &element, &mower_map.AddMowingAreaSrvRes{})\n\t\t\tif err != nil {\n\t\t\t\tc.JSON(500, ErrorResponse{Error: err.Error()})\n\t\t\t\treturn\n\t\t\t}\n\t\t}\n\n\t\tc.JSON(200, OkResponse{})\n\t})\n}\n'''

replace_once(openmower, old_replace_route, new_replace_route)

replace_once(
    map_area,
    '''type MapArea struct {\n\tmsg.Package `ros:"mower_map"`\n\tName        string\n\tArea        geometry_msgs.Polygon\n\tObstacles   []geometry_msgs.Polygon\n}\n''',
    '''type MapArea struct {\n\tmsg.Package         `ros:"mower_map"`\n\tName                string\n\tActive              bool\n\tArea                geometry_msgs.Polygon\n\tObstacles           []geometry_msgs.Polygon\n\tAngle               float64\n\tOutlineCount        int32   `rosname:"outline_count"`\n\tOutlineOverlapCount int32   `rosname:"outline_overlap_count"`\n\tOutlineOffset       float64 `rosname:"outline_offset"`\n}\n''',
)

print("OpenMower GUI compatibility changes applied successfully")
