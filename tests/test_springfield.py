from flyforecast.springfield import hourly, build
from flyforecast.config import load_sites

def fixture(sun=600):
    return dict(time=['2026-07-01T13:00'],temperature_2m=[25],dew_point_2m=[12],shortwave_radiation=[sun],wind_speed_10m=[10],wind_direction_10m=[35],temperature_950hPa=[19],geopotential_height_950hPa=[600],temperature_900hPa=[19],geopotential_height_900hPa=[1100])

def test_hour():
    r=hourly(load_sites("springfield.yaml")[0],fixture(),0)
    assert r['lift_agl']>0 and r['wstar_kt']>0 and r['crosswind']['35']==0

def test_night():
    r=hourly(load_sites("springfield.yaml")[0],fixture(0),0)
    assert r['lift_agl']==0 and r['wstar_kt']==0

def test_build(tmp_path):
    r=build(lambda *a:{'gfs_global':fixture()},tmp_path,False)
    assert 'gfs_global' in r['models'] and (tmp_path/'index.html').exists()
