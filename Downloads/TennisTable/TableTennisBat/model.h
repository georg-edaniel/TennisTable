// ============================================================
// model.h — Classifieur de coups TT (généré automatiquement)
// RandomForest → vote majoritaire entre N arbres
// Classes : BHdrive=0  BHsmash=1  FHdrive=2  FHloop=3
//           FHsmash=4  zzz=5 (repos)
// ============================================================
#pragma once
#define N_FEATURES 16
#define N_CLASSES  6
#define N_TREES    15

static int tree_0(const float* f) {
if (f[12] <= 6111.980652f) {  // energy_gyro
  return 5;  // zzz
} else {
  if (f[9] <= 0.785500f) {  // peak_ax
    if (f[2] <= 34.305510f) {  // peak_gy
      if (f[11] <= 1.043200f) {  // peak_az
        return 3;  // FHloop
      } else {
        return 3;  // FHloop
      }
    } else {
      if (f[6] <= 9.805184f) {  // mean_gz
        if (f[6] <= 7.025331f) {  // mean_gz
          return 4;  // FHsmash
        } else {
          if (f[5] <= 17.301399f) {  // mean_gy
            return 0;  // BHdrive
          } else {
            return 2;  // FHdrive
          }
        }
      } else {
        if (f[14] <= 2.727991f) {  // ratio_gx_gy
          if (f[7] <= 57.196606f) {  // rms_gyro
            return 0;  // BHdrive
          } else {
            return 2;  // FHdrive
          }
        } else {
          return 0;  // BHdrive
        }
      }
    }
  } else {
    if (f[7] <= 198.406952f) {  // rms_gyro
      if (f[8] <= 1.450411f) {  // peak_accel_mag
        if (f[12] <= 233065.796875f) {  // energy_gyro
          if (f[10] <= 0.718066f) {  // peak_ay
            return 1;  // BHsmash
          } else {
            return 1;  // BHsmash
          }
        } else {
          return 1;  // BHsmash
        }
      } else {
        if (f[9] <= 1.638086f) {  // peak_ax
          if (f[8] <= 1.701501f) {  // peak_accel_mag
            if (f[1] <= -369.093323f) {  // peak_gx
              if (f[3] <= 94.000076f) {  // peak_gz
                return 4;  // FHsmash
              } else {
                return 4;  // FHsmash
              }
            } else {
              if (f[11] <= 0.604570f) {  // peak_az
                return 4;  // FHsmash
              } else {
                if (f[1] <= 340.010284f) {  // peak_gx
                  return 1;  // BHsmash
                } else {
                  if (f[0] <= 397.379562f) {  // peak_gyro_mag
                    return 4;  // FHsmash
                  } else {
                    return 1;  // BHsmash
                  }
                }
              }
            }
          } else {
            if (f[3] <= 176.604820f) {  // peak_gz
              return 4;  // FHsmash
            } else {
              return 4;  // FHsmash
            }
          }
        } else {
          if (f[2] <= 311.365112f) {  // peak_gy
            if (f[3] <= 211.017113f) {  // peak_gz
              return 1;  // BHsmash
            } else {
              return 4;  // FHsmash
            }
          } else {
            if (f[11] <= 0.370436f) {  // peak_az
              return 4;  // FHsmash
            } else {
              return 1;  // BHsmash
            }
          }
        }
      }
    } else {
      if (f[9] <= 2.223049f) {  // peak_ax
        if (f[2] <= 301.953445f) {  // peak_gy
          if (f[9] <= 1.804527f) {  // peak_ax
            if (f[13] <= 0.250000f) {  // peak_timing
              return 1;  // BHsmash
            } else {
              return 4;  // FHsmash
            }
          } else {
            if (f[11] <= 0.377198f) {  // peak_az
              if (f[14] <= -2.653834f) {  // ratio_gx_gy
                return 4;  // FHsmash
              } else {
                return 1;  // BHsmash
              }
            } else {
              return 1;  // BHsmash
            }
          }
        } else {
          if (f[10] <= 1.077034f) {  // peak_ay
            if (f[10] <= 1.021159f) {  // peak_ay
              return 4;  // FHsmash
            } else {
              return 1;  // BHsmash
            }
          } else {
            return 4;  // FHsmash
          }
        }
      } else {
        return 4;  // FHsmash
      }
    }
  }
}
}

static int tree_1(const float* f) {
if (f[2] <= 34.305510f) {  // peak_gy
  if (f[12] <= 98614.839050f) {  // energy_gyro
    return 5;  // zzz
  } else {
    return 3;  // FHloop
  }
} else {
  if (f[11] <= 0.743175f) {  // peak_az
    if (f[11] <= 0.372328f) {  // peak_az
      if (f[5] <= 43.530804f) {  // mean_gy
        if (f[0] <= 635.104919f) {  // peak_gyro_mag
          return 1;  // BHsmash
        } else {
          if (f[0] <= 717.690826f) {  // peak_gyro_mag
            if (f[10] <= 0.888415f) {  // peak_ay
              return 1;  // BHsmash
            } else {
              if (f[1] <= -557.897552f) {  // peak_gx
                return 4;  // FHsmash
              } else {
                return 4;  // FHsmash
              }
            }
          } else {
            return 4;  // FHsmash
          }
        }
      } else {
        return 1;  // BHsmash
      }
    } else {
      if (f[3] <= 215.757729f) {  // peak_gz
        if (f[0] <= 758.060791f) {  // peak_gyro_mag
          if (f[14] <= -2.608599f) {  // ratio_gx_gy
            if (f[9] <= 1.529649f) {  // peak_ax
              if (f[12] <= 454796.656250f) {  // energy_gyro
                return 1;  // BHsmash
              } else {
                return 4;  // FHsmash
              }
            } else {
              return 1;  // BHsmash
            }
          } else {
            if (f[9] <= 1.578947f) {  // peak_ax
              if (f[8] <= 1.468917f) {  // peak_accel_mag
                if (f[1] <= -314.355011f) {  // peak_gx
                  return 1;  // BHsmash
                } else {
                  return 1;  // BHsmash
                }
              } else {
                if (f[8] <= 1.550661f) {  // peak_accel_mag
                  return 4;  // FHsmash
                } else {
                  if (f[2] <= 187.580124f) {  // peak_gy
                    if (f[13] <= 0.312500f) {  // peak_timing
                      return 1;  // BHsmash
                    } else {
                      if (f[8] <= 1.591309f) {  // peak_accel_mag
                        return 1;  // BHsmash
                      } else {
                        return 1;  // BHsmash
                      }
                    }
                  } else {
                    if (f[6] <= 20.109819f) {  // mean_gz
                      if (f[9] <= 1.375279f) {  // peak_ax
                        return 1;  // BHsmash
                      } else {
                        return 1;  // BHsmash
                      }
                    } else {
                      return 4;  // FHsmash
                    }
                  }
                }
              }
            } else {
              if (f[7] <= 197.376503f) {  // rms_gyro
                return 1;  // BHsmash
              } else {
                if (f[5] <= 37.539059f) {  // mean_gy
                  return 1;  // BHsmash
                } else {
                  return 1;  // BHsmash
                }
              }
            }
          }
        } else {
          return 4;  // FHsmash
        }
      } else {
        return 4;  // FHsmash
      }
    }
  } else {
    if (f[7] <= 58.239067f) {  // rms_gyro
      if (f[7] <= 49.913021f) {  // rms_gyro
        return 0;  // BHdrive
      } else {
        return 0;  // BHdrive
      }
    } else {
      return 2;  // FHdrive
    }
  }
}
}

static int tree_2(const float* f) {
if (f[12] <= 6111.980652f) {  // energy_gyro
  return 5;  // zzz
} else {
  if (f[2] <= 26.387854f) {  // peak_gy
    return 3;  // FHloop
  } else {
    if (f[10] <= 0.467379f) {  // peak_ay
      if (f[5] <= 16.179523f) {  // mean_gy
        if (f[5] <= 11.320319f) {  // mean_gy
          if (f[7] <= 38.641096f) {  // rms_gyro
            return 1;  // BHsmash
          } else {
            return 4;  // FHsmash
          }
        } else {
          return 0;  // BHdrive
        }
      } else {
        if (f[7] <= 57.431759f) {  // rms_gyro
          return 0;  // BHdrive
        } else {
          return 2;  // FHdrive
        }
      }
    } else {
      if (f[9] <= 2.248549f) {  // peak_ax
        if (f[3] <= 216.747307f) {  // peak_gz
          if (f[4] <= -13.981460f) {  // mean_gx
            if (f[10] <= 1.223413f) {  // peak_ay
              if (f[0] <= 421.609314f) {  // peak_gyro_mag
                if (f[0] <= 385.482712f) {  // peak_gyro_mag
                  return 1;  // BHsmash
                } else {
                  return 1;  // BHsmash
                }
              } else {
                if (f[0] <= 504.470688f) {  // peak_gyro_mag
                  return 4;  // FHsmash
                } else {
                  if (f[11] <= 0.395925f) {  // peak_az
                    if (f[7] <= 149.826210f) {  // rms_gyro
                      return 1;  // BHsmash
                    } else {
                      if (f[14] <= -2.267566f) {  // ratio_gx_gy
                        return 4;  // FHsmash
                      } else {
                        return 4;  // FHsmash
                      }
                    }
                  } else {
                    return 1;  // BHsmash
                  }
                }
              }
            } else {
              return 1;  // BHsmash
            }
          } else {
            if (f[1] <= 668.530853f) {  // peak_gx
              if (f[11] <= 0.525496f) {  // peak_az
                if (f[2] <= 324.787277f) {  // peak_gy
                  if (f[8] <= 2.005850f) {  // peak_accel_mag
                    if (f[11] <= 0.366595f) {  // peak_az
                      return 4;  // FHsmash
                    } else {
                      return 1;  // BHsmash
                    }
                  } else {
                    return 1;  // BHsmash
                  }
                } else {
                  return 4;  // FHsmash
                }
              } else {
                if (f[2] <= 189.689545f) {  // peak_gy
                  if (f[5] <= 10.524699f) {  // mean_gy
                    return 4;  // FHsmash
                  } else {
                    if (f[13] <= 0.229167f) {  // peak_timing
                      if (f[8] <= 1.453647f) {  // peak_accel_mag
                        return 1;  // BHsmash
                      } else {
                        return 4;  // FHsmash
                      }
                    } else {
                      return 1;  // BHsmash
                    }
                  }
                } else {
                  return 4;  // FHsmash
                }
              }
            } else {
              return 4;  // FHsmash
            }
          }
        } else {
          return 4;  // FHsmash
        }
      } else {
        return 4;  // FHsmash
      }
    }
  }
}
}

static int tree_3(const float* f) {
if (f[7] <= 21.488476f) {  // rms_gyro
  return 5;  // zzz
} else {
  if (f[0] <= 237.929779f) {  // peak_gyro_mag
    if (f[7] <= 79.797863f) {  // rms_gyro
      if (f[7] <= 57.692949f) {  // rms_gyro
        if (f[7] <= 48.000818f) {  // rms_gyro
          return 4;  // FHsmash
        } else {
          return 0;  // BHdrive
        }
      } else {
        return 2;  // FHdrive
      }
    } else {
      return 3;  // FHloop
    }
  } else {
    if (f[0] <= 458.941788f) {  // peak_gyro_mag
      if (f[1] <= -369.093323f) {  // peak_gx
        if (f[1] <= -377.884293f) {  // peak_gx
          return 1;  // BHsmash
        } else {
          return 4;  // FHsmash
        }
      } else {
        if (f[5] <= 13.114604f) {  // mean_gy
          if (f[3] <= 111.507168f) {  // peak_gz
            return 1;  // BHsmash
          } else {
            if (f[9] <= 1.140070f) {  // peak_ax
              return 1;  // BHsmash
            } else {
              return 4;  // FHsmash
            }
          }
        } else {
          if (f[4] <= -31.980028f) {  // mean_gx
            return 1;  // BHsmash
          } else {
            if (f[7] <= 86.386303f) {  // rms_gyro
              return 1;  // BHsmash
            } else {
              if (f[0] <= 387.627914f) {  // peak_gyro_mag
                if (f[10] <= 0.737050f) {  // peak_ay
                  return 1;  // BHsmash
                } else {
                  return 1;  // BHsmash
                }
              } else {
                return 1;  // BHsmash
              }
            }
          }
        }
      }
    } else {
      if (f[11] <= 0.365042f) {  // peak_az
        if (f[14] <= -2.931409f) {  // ratio_gx_gy
          return 1;  // BHsmash
        } else {
          return 4;  // FHsmash
        }
      } else {
        if (f[2] <= 304.715256f) {  // peak_gy
          if (f[0] <= 527.260101f) {  // peak_gyro_mag
            return 4;  // FHsmash
          } else {
            if (f[0] <= 747.378998f) {  // peak_gyro_mag
              if (f[14] <= 2.156815f) {  // ratio_gx_gy
                return 1;  // BHsmash
              } else {
                if (f[0] <= 687.740265f) {  // peak_gyro_mag
                  return 1;  // BHsmash
                } else {
                  return 4;  // FHsmash
                }
              }
            } else {
              return 4;  // FHsmash
            }
          }
        } else {
          if (f[6] <= 17.001778f) {  // mean_gz
            return 1;  // BHsmash
          } else {
            if (f[4] <= -54.545092f) {  // mean_gx
              return 1;  // BHsmash
            } else {
              return 4;  // FHsmash
            }
          }
        }
      }
    }
  }
}
}

static int tree_4(const float* f) {
if (f[10] <= 0.508337f) {  // peak_ay
  if (f[11] <= 1.043824f) {  // peak_az
    if (f[7] <= 79.574394f) {  // rms_gyro
      if (f[6] <= 9.778483f) {  // mean_gz
        if (f[12] <= 85171.531250f) {  // energy_gyro
          if (f[12] <= 64108.615234f) {  // energy_gyro
            return 0;  // BHdrive
          } else {
            return 0;  // BHdrive
          }
        } else {
          return 2;  // FHdrive
        }
      } else {
        if (f[7] <= 57.324348f) {  // rms_gyro
          return 0;  // BHdrive
        } else {
          return 2;  // FHdrive
        }
      }
    } else {
      return 3;  // FHloop
    }
  } else {
    if (f[12] <= 18120.958191f) {  // energy_gyro
      return 5;  // zzz
    } else {
      if (f[13] <= 0.250000f) {  // peak_timing
        return 3;  // FHloop
      } else {
        return 1;  // BHsmash
      }
    }
  }
} else {
  if (f[3] <= 216.919785f) {  // peak_gz
    if (f[8] <= 2.603848f) {  // peak_accel_mag
      if (f[10] <= 1.217512f) {  // peak_ay
        if (f[2] <= 299.715424f) {  // peak_gy
          if (f[8] <= 1.797663f) {  // peak_accel_mag
            if (f[11] <= 0.604570f) {  // peak_az
              if (f[2] <= 212.644630f) {  // peak_gy
                return 4;  // FHsmash
              } else {
                return 1;  // BHsmash
              }
            } else {
              if (f[7] <= 164.646729f) {  // rms_gyro
                if (f[0] <= 439.970444f) {  // peak_gyro_mag
                  if (f[4] <= 2.706016f) {  // mean_gx
                    return 1;  // BHsmash
                  } else {
                    if (f[4] <= 5.707680f) {  // mean_gx
                      return 4;  // FHsmash
                    } else {
                      return 1;  // BHsmash
                    }
                  }
                } else {
                  if (f[1] <= 9.475189f) {  // peak_gx
                    return 4;  // FHsmash
                  } else {
                    return 4;  // FHsmash
                  }
                }
              } else {
                return 4;  // FHsmash
              }
            }
          } else {
            if (f[1] <= -660.960144f) {  // peak_gx
              return 4;  // FHsmash
            } else {
              if (f[14] <= 1.966417f) {  // ratio_gx_gy
                if (f[3] <= 206.289726f) {  // peak_gz
                  return 1;  // BHsmash
                } else {
                  return 1;  // BHsmash
                }
              } else {
                if (f[13] <= 0.333333f) {  // peak_timing
                  if (f[1] <= 669.288696f) {  // peak_gx
                    return 1;  // BHsmash
                  } else {
                    return 1;  // BHsmash
                  }
                } else {
                  return 4;  // FHsmash
                }
              }
            }
          }
        } else {
          if (f[10] <= 1.085336f) {  // peak_ay
            if (f[10] <= 0.996690f) {  // peak_ay
              return 4;  // FHsmash
            } else {
              if (f[13] <= 0.229167f) {  // peak_timing
                return 1;  // BHsmash
              } else {
                return 1;  // BHsmash
              }
            }
          } else {
            return 4;  // FHsmash
          }
        }
      } else {
        if (f[13] <= 0.229167f) {  // peak_timing
          if (f[4] <= 18.825429f) {  // mean_gx
            return 1;  // BHsmash
          } else {
            return 1;  // BHsmash
          }
        } else {
          return 1;  // BHsmash
        }
      }
    } else {
      return 4;  // FHsmash
    }
  } else {
    return 4;  // FHsmash
  }
}
}

static int tree_5(const float* f) {
if (f[12] <= 18120.958191f) {  // energy_gyro
  return 5;  // zzz
} else {
  if (f[7] <= 57.812920f) {  // rms_gyro
    if (f[5] <= 11.368622f) {  // mean_gy
      if (f[0] <= 108.529804f) {  // peak_gyro_mag
        return 4;  // FHsmash
      } else {
        return 4;  // FHsmash
      }
    } else {
      return 0;  // BHdrive
    }
  } else {
    if (f[2] <= 33.010080f) {  // peak_gy
      return 3;  // FHloop
    } else {
      if (f[10] <= 0.467607f) {  // peak_ay
        return 2;  // FHdrive
      } else {
        if (f[0] <= 747.378998f) {  // peak_gyro_mag
          if (f[2] <= 321.368134f) {  // peak_gy
            if (f[8] <= 2.087035f) {  // peak_accel_mag
              if (f[1] <= -380.776947f) {  // peak_gx
                if (f[0] <= 531.538635f) {  // peak_gyro_mag
                  return 4;  // FHsmash
                } else {
                  if (f[11] <= 0.362001f) {  // peak_az
                    return 4;  // FHsmash
                  } else {
                    return 1;  // BHsmash
                  }
                }
              } else {
                if (f[12] <= 171490.281250f) {  // energy_gyro
                  return 1;  // BHsmash
                } else {
                  if (f[6] <= 8.851222f) {  // mean_gz
                    return 4;  // FHsmash
                  } else {
                    if (f[12] <= 299234.937500f) {  // energy_gyro
                      return 1;  // BHsmash
                    } else {
                      if (f[4] <= 10.637707f) {  // mean_gx
                        return 4;  // FHsmash
                      } else {
                        return 1;  // BHsmash
                      }
                    }
                  }
                }
              }
            } else {
              if (f[2] <= 312.539886f) {  // peak_gy
                if (f[6] <= 21.563382f) {  // mean_gz
                  return 1;  // BHsmash
                } else {
                  if (f[13] <= 0.354167f) {  // peak_timing
                    if (f[4] <= 9.869714f) {  // mean_gx
                      return 1;  // BHsmash
                    } else {
                      return 4;  // FHsmash
                    }
                  } else {
                    return 4;  // FHsmash
                  }
                }
              } else {
                return 4;  // FHsmash
              }
            }
          } else {
            return 4;  // FHsmash
          }
        } else {
          return 4;  // FHsmash
        }
      }
    }
  }
}
}

static int tree_6(const float* f) {
if (f[0] <= 42.324911f) {  // peak_gyro_mag
  return 5;  // zzz
} else {
  if (f[10] <= 0.485851f) {  // peak_ay
    if (f[7] <= 78.909843f) {  // rms_gyro
      if (f[5] <= 16.181725f) {  // mean_gy
        if (f[12] <= 57695.287109f) {  // energy_gyro
          if (f[2] <= 40.157633f) {  // peak_gy
            return 1;  // BHsmash
          } else {
            return 4;  // FHsmash
          }
        } else {
          return 0;  // BHdrive
        }
      } else {
        if (f[10] <= 0.282418f) {  // peak_ay
          return 0;  // BHdrive
        } else {
          return 2;  // FHdrive
        }
      }
    } else {
      return 3;  // FHloop
    }
  } else {
    if (f[2] <= 323.238098f) {  // peak_gy
      if (f[1] <= 571.622040f) {  // peak_gx
        if (f[9] <= 1.789826f) {  // peak_ax
          if (f[1] <= -380.776947f) {  // peak_gx
            if (f[0] <= 531.538635f) {  // peak_gyro_mag
              return 4;  // FHsmash
            } else {
              if (f[5] <= 27.626010f) {  // mean_gy
                return 1;  // BHsmash
              } else {
                if (f[14] <= -2.031332f) {  // ratio_gx_gy
                  return 4;  // FHsmash
                } else {
                  return 1;  // BHsmash
                }
              }
            }
          } else {
            if (f[4] <= 2.665728f) {  // mean_gx
              if (f[12] <= 188275.453125f) {  // energy_gyro
                return 1;  // BHsmash
              } else {
                return 1;  // BHsmash
              }
            } else {
              if (f[1] <= 413.636795f) {  // peak_gx
                if (f[14] <= 1.636319f) {  // ratio_gx_gy
                  if (f[9] <= 1.197336f) {  // peak_ax
                    return 4;  // FHsmash
                  } else {
                    return 1;  // BHsmash
                  }
                } else {
                  if (f[3] <= 109.336750f) {  // peak_gz
                    return 1;  // BHsmash
                  } else {
                    if (f[12] <= 435783.968750f) {  // energy_gyro
                      return 4;  // FHsmash
                    } else {
                      return 1;  // BHsmash
                    }
                  }
                }
              } else {
                if (f[2] <= 308.276031f) {  // peak_gy
                  return 4;  // FHsmash
                } else {
                  return 1;  // BHsmash
                }
              }
            }
          }
        } else {
          if (f[0] <= 724.428680f) {  // peak_gyro_mag
            if (f[8] <= 2.570487f) {  // peak_accel_mag
              if (f[11] <= 0.345521f) {  // peak_az
                return 1;  // BHsmash
              } else {
                return 1;  // BHsmash
              }
            } else {
              return 1;  // BHsmash
            }
          } else {
            if (f[6] <= 24.192834f) {  // mean_gz
              return 1;  // BHsmash
            } else {
              return 1;  // BHsmash
            }
          }
        }
      } else {
        if (f[11] <= 0.404128f) {  // peak_az
          return 4;  // FHsmash
        } else {
          if (f[8] <= 2.274360f) {  // peak_accel_mag
            return 1;  // BHsmash
          } else {
            return 1;  // BHsmash
          }
        }
      }
    } else {
      return 4;  // FHsmash
    }
  }
}
}

static int tree_7(const float* f) {
if (f[8] <= 1.269290f) {  // peak_accel_mag
  if (f[7] <= 57.692949f) {  // rms_gyro
    if (f[6] <= 7.025331f) {  // mean_gz
      if (f[4] <= 2.898745f) {  // mean_gx
        return 5;  // zzz
      } else {
        return 4;  // FHsmash
      }
    } else {
      return 0;  // BHdrive
    }
  } else {
    if (f[0] <= 120.231335f) {  // peak_gyro_mag
      return 3;  // FHloop
    } else {
      return 2;  // FHdrive
    }
  }
} else {
  if (f[3] <= 216.616241f) {  // peak_gz
    if (f[11] <= 0.345436f) {  // peak_az
      return 4;  // FHsmash
    } else {
      if (f[6] <= 11.024004f) {  // mean_gz
        if (f[8] <= 1.468114f) {  // peak_accel_mag
          if (f[8] <= 1.397751f) {  // peak_accel_mag
            return 1;  // BHsmash
          } else {
            return 1;  // BHsmash
          }
        } else {
          if (f[12] <= 217231.179688f) {  // energy_gyro
            if (f[11] <= 0.611820f) {  // peak_az
              return 4;  // FHsmash
            } else {
              return 1;  // BHsmash
            }
          } else {
            return 4;  // FHsmash
          }
        }
      } else {
        if (f[1] <= 689.448151f) {  // peak_gx
          if (f[2] <= 310.160568f) {  // peak_gy
            if (f[14] <= -2.595511f) {  // ratio_gx_gy
              if (f[12] <= 925132.062500f) {  // energy_gyro
                return 4;  // FHsmash
              } else {
                return 1;  // BHsmash
              }
            } else {
              if (f[3] <= 151.864586f) {  // peak_gz
                if (f[0] <= 441.876389f) {  // peak_gyro_mag
                  if (f[3] <= 111.804905f) {  // peak_gz
                    return 1;  // BHsmash
                  } else {
                    if (f[2] <= 149.360626f) {  // peak_gy
                      if (f[2] <= 130.827076f) {  // peak_gy
                        return 1;  // BHsmash
                      } else {
                        return 4;  // FHsmash
                      }
                    } else {
                      return 1;  // BHsmash
                    }
                  }
                } else {
                  if (f[9] <= 1.784304f) {  // peak_ax
                    if (f[12] <= 564789.875000f) {  // energy_gyro
                      return 4;  // FHsmash
                    } else {
                      if (f[6] <= 19.808991f) {  // mean_gz
                        return 1;  // BHsmash
                      } else {
                        return 4;  // FHsmash
                      }
                    }
                  } else {
                    return 1;  // BHsmash
                  }
                }
              } else {
                if (f[4] <= 46.708609f) {  // mean_gx
                  return 1;  // BHsmash
                } else {
                  return 1;  // BHsmash
                }
              }
            }
          } else {
            if (f[0] <= 706.530609f) {  // peak_gyro_mag
              if (f[12] <= 598634.593750f) {  // energy_gyro
                return 1;  // BHsmash
              } else {
                return 1;  // BHsmash
              }
            } else {
              return 4;  // FHsmash
            }
          }
        } else {
          return 4;  // FHsmash
        }
      }
    }
  } else {
    return 4;  // FHsmash
  }
}
}

static int tree_8(const float* f) {
if (f[12] <= 6111.980652f) {  // energy_gyro
  return 5;  // zzz
} else {
  if (f[12] <= 82904.023438f) {  // energy_gyro
    if (f[6] <= 6.486672f) {  // mean_gz
      if (f[9] <= -0.006537f) {  // peak_ax
        return 1;  // BHsmash
      } else {
        return 4;  // FHsmash
      }
    } else {
      return 0;  // BHdrive
    }
  } else {
    if (f[7] <= 70.268112f) {  // rms_gyro
      return 2;  // FHdrive
    } else {
      if (f[0] <= 216.286442f) {  // peak_gyro_mag
        return 3;  // FHloop
      } else {
        if (f[3] <= 215.114738f) {  // peak_gz
          if (f[1] <= -369.093323f) {  // peak_gx
            if (f[11] <= 0.525496f) {  // peak_az
              if (f[8] <= 2.406422f) {  // peak_accel_mag
                if (f[14] <= -2.857892f) {  // ratio_gx_gy
                  if (f[4] <= -22.414396f) {  // mean_gx
                    return 4;  // FHsmash
                  } else {
                    return 1;  // BHsmash
                  }
                } else {
                  if (f[7] <= 224.902557f) {  // rms_gyro
                    return 1;  // BHsmash
                  } else {
                    return 1;  // BHsmash
                  }
                }
              } else {
                if (f[13] <= 0.229167f) {  // peak_timing
                  return 1;  // BHsmash
                } else {
                  return 4;  // FHsmash
                }
              }
            } else {
              if (f[0] <= 433.180481f) {  // peak_gyro_mag
                return 1;  // BHsmash
              } else {
                return 4;  // FHsmash
              }
            }
          } else {
            if (f[9] <= 1.213896f) {  // peak_ax
              return 1;  // BHsmash
            } else {
              if (f[13] <= 0.312500f) {  // peak_timing
                if (f[7] <= 193.882545f) {  // rms_gyro
                  if (f[13] <= 0.270833f) {  // peak_timing
                    if (f[10] <= 0.820200f) {  // peak_ay
                      if (f[2] <= 150.371101f) {  // peak_gy
                        return 1;  // BHsmash
                      } else {
                        return 4;  // FHsmash
                      }
                    } else {
                      return 1;  // BHsmash
                    }
                  } else {
                    return 1;  // BHsmash
                  }
                } else {
                  if (f[5] <= 44.829983f) {  // mean_gy
                    if (f[11] <= 0.357022f) {  // peak_az
                      return 4;  // FHsmash
                    } else {
                      return 1;  // BHsmash
                    }
                  } else {
                    return 4;  // FHsmash
                  }
                }
              } else {
                if (f[7] <= 113.834129f) {  // rms_gyro
                  if (f[12] <= 167866.085938f) {  // energy_gyro
                    return 1;  // BHsmash
                  } else {
                    return 4;  // FHsmash
                  }
                } else {
                  if (f[1] <= 427.562210f) {  // peak_gx
                    return 1;  // BHsmash
                  } else {
                    if (f[8] <= 2.315884f) {  // peak_accel_mag
                      return 4;  // FHsmash
                    } else {
                      if (f[6] <= 22.276666f) {  // mean_gz
                        return 1;  // BHsmash
                      } else {
                        return 1;  // BHsmash
                      }
                    }
                  }
                }
              }
            }
          }
        } else {
          if (f[6] <= 19.552906f) {  // mean_gz
            return 1;  // BHsmash
          } else {
            return 4;  // FHsmash
          }
        }
      }
    }
  }
}
}

static int tree_9(const float* f) {
if (f[12] <= 6107.111038f) {  // energy_gyro
  return 5;  // zzz
} else {
  if (f[9] <= 0.816574f) {  // peak_ax
    if (f[6] <= 7.611756f) {  // mean_gz
      if (f[11] <= 1.051902f) {  // peak_az
        if (f[7] <= 90.905262f) {  // rms_gyro
          return 3;  // FHloop
        } else {
          return 3;  // FHloop
        }
      } else {
        return 1;  // BHsmash
      }
    } else {
      if (f[7] <= 58.398796f) {  // rms_gyro
        return 0;  // BHdrive
      } else {
        if (f[9] <= 0.260277f) {  // peak_ax
          return 3;  // FHloop
        } else {
          return 2;  // FHdrive
        }
      }
    }
  } else {
    if (f[11] <= 0.365274f) {  // peak_az
      if (f[12] <= 538136.937500f) {  // energy_gyro
        return 1;  // BHsmash
      } else {
        if (f[6] <= 19.239296f) {  // mean_gz
          if (f[5] <= 25.230626f) {  // mean_gy
            return 4;  // FHsmash
          } else {
            if (f[9] <= 2.074078f) {  // peak_ax
              return 4;  // FHsmash
            } else {
              return 1;  // BHsmash
            }
          }
        } else {
          return 4;  // FHsmash
        }
      }
    } else {
      if (f[0] <= 727.035828f) {  // peak_gyro_mag
        if (f[11] <= 0.520427f) {  // peak_az
          if (f[12] <= 821488.093750f) {  // energy_gyro
            return 1;  // BHsmash
          } else {
            if (f[2] <= 338.701843f) {  // peak_gy
              if (f[4] <= 30.946520f) {  // mean_gx
                return 1;  // BHsmash
              } else {
                return 1;  // BHsmash
              }
            } else {
              return 4;  // FHsmash
            }
          }
        } else {
          if (f[9] <= 1.368753f) {  // peak_ax
            if (f[1] <= -389.781219f) {  // peak_gx
              return 4;  // FHsmash
            } else {
              if (f[11] <= 0.597251f) {  // peak_az
                return 4;  // FHsmash
              } else {
                if (f[4] <= -33.374670f) {  // mean_gx
                  return 4;  // FHsmash
                } else {
                  if (f[5] <= 17.287678f) {  // mean_gy
                    return 1;  // BHsmash
                  } else {
                    if (f[5] <= 18.621870f) {  // mean_gy
                      return 4;  // FHsmash
                    } else {
                      if (f[1] <= 400.629807f) {  // peak_gx
                        return 1;  // BHsmash
                      } else {
                        return 1;  // BHsmash
                      }
                    }
                  }
                }
              }
            }
          } else {
            return 4;  // FHsmash
          }
        }
      } else {
        if (f[9] <= 1.600808f) {  // peak_ax
          return 1;  // BHsmash
        } else {
          return 4;  // FHsmash
        }
      }
    }
  }
}
}

static int tree_10(const float* f) {
if (f[7] <= 12.712217f) {  // rms_gyro
  return 5;  // zzz
} else {
  if (f[12] <= 120722.730469f) {  // energy_gyro
    if (f[11] <= 0.839043f) {  // peak_az
      if (f[12] <= 84816.421875f) {  // energy_gyro
        return 0;  // BHdrive
      } else {
        return 2;  // FHdrive
      }
    } else {
      if (f[5] <= 16.679276f) {  // mean_gy
        if (f[6] <= 7.025331f) {  // mean_gz
          if (f[6] <= 5.274688f) {  // mean_gz
            return 1;  // BHsmash
          } else {
            return 4;  // FHsmash
          }
        } else {
          if (f[7] <= 59.139753f) {  // rms_gyro
            return 0;  // BHdrive
          } else {
            return 2;  // FHdrive
          }
        }
      } else {
        return 2;  // FHdrive
      }
    }
  } else {
    if (f[10] <= 0.364364f) {  // peak_ay
      return 3;  // FHloop
    } else {
      if (f[7] <= 216.731705f) {  // rms_gyro
        if (f[9] <= 2.252783f) {  // peak_ax
          if (f[11] <= 0.355935f) {  // peak_az
            if (f[10] <= 0.976381f) {  // peak_ay
              return 1;  // BHsmash
            } else {
              return 4;  // FHsmash
            }
          } else {
            if (f[8] <= 1.837106f) {  // peak_accel_mag
              if (f[0] <= 444.887695f) {  // peak_gyro_mag
                if (f[5] <= 20.832627f) {  // mean_gy
                  if (f[1] <= 340.010284f) {  // peak_gx
                    if (f[11] <= 0.599721f) {  // peak_az
                      return 4;  // FHsmash
                    } else {
                      if (f[4] <= -15.111968f) {  // mean_gx
                        return 1;  // BHsmash
                      } else {
                        return 1;  // BHsmash
                      }
                    }
                  } else {
                    if (f[12] <= 236453.968750f) {  // energy_gyro
                      return 4;  // FHsmash
                    } else {
                      return 4;  // FHsmash
                    }
                  }
                } else {
                  return 1;  // BHsmash
                }
              } else {
                if (f[3] <= 151.600487f) {  // peak_gz
                  if (f[5] <= 28.804397f) {  // mean_gy
                    return 4;  // FHsmash
                  } else {
                    if (f[2] <= 169.090172f) {  // peak_gy
                      return 1;  // BHsmash
                    } else {
                      return 4;  // FHsmash
                    }
                  }
                } else {
                  return 1;  // BHsmash
                }
              }
            } else {
              if (f[2] <= 322.224350f) {  // peak_gy
                if (f[14] <= 1.985003f) {  // ratio_gx_gy
                  if (f[12] <= 1106076.687500f) {  // energy_gyro
                    return 1;  // BHsmash
                  } else {
                    return 1;  // BHsmash
                  }
                } else {
                  if (f[7] <= 180.016159f) {  // rms_gyro
                    return 1;  // BHsmash
                  } else {
                    if (f[9] <= 1.688123f) {  // peak_ax
                      return 1;  // BHsmash
                    } else {
                      return 1;  // BHsmash
                    }
                  }
                }
              } else {
                return 4;  // FHsmash
              }
            }
          }
        } else {
          return 4;  // FHsmash
        }
      } else {
        if (f[8] <= 2.529269f) {  // peak_accel_mag
          return 4;  // FHsmash
        } else {
          if (f[2] <= 301.957458f) {  // peak_gy
            if (f[5] <= 37.583057f) {  // mean_gy
              return 4;  // FHsmash
            } else {
              return 1;  // BHsmash
            }
          } else {
            return 4;  // FHsmash
          }
        }
      }
    }
  }
}
}

static int tree_11(const float* f) {
if (f[9] <= 0.785500f) {  // peak_ax
  if (f[12] <= 6103.769455f) {  // energy_gyro
    return 5;  // zzz
  } else {
    if (f[2] <= 25.076640f) {  // peak_gy
      return 3;  // FHloop
    } else {
      if (f[5] <= 16.157927f) {  // mean_gy
        if (f[6] <= 7.025331f) {  // mean_gz
          if (f[3] <= 31.941966f) {  // peak_gz
            return 1;  // BHsmash
          } else {
            return 4;  // FHsmash
          }
        } else {
          return 0;  // BHdrive
        }
      } else {
        if (f[6] <= 9.184566f) {  // mean_gz
          return 0;  // BHdrive
        } else {
          return 2;  // FHdrive
        }
      }
    }
  }
} else {
  if (f[3] <= 214.840195f) {  // peak_gz
    if (f[0] <= 713.354279f) {  // peak_gyro_mag
      if (f[8] <= 2.171181f) {  // peak_accel_mag
        if (f[8] <= 1.450206f) {  // peak_accel_mag
          if (f[5] <= 13.488279f) {  // mean_gy
            return 4;  // FHsmash
          } else {
            return 1;  // BHsmash
          }
        } else {
          if (f[0] <= 458.941788f) {  // peak_gyro_mag
            if (f[11] <= 0.599103f) {  // peak_az
              return 4;  // FHsmash
            } else {
              if (f[12] <= 186852.851562f) {  // energy_gyro
                return 1;  // BHsmash
              } else {
                if (f[0] <= 437.120895f) {  // peak_gyro_mag
                  return 1;  // BHsmash
                } else {
                  return 1;  // BHsmash
                }
              }
            }
          } else {
            if (f[10] <= 1.145193f) {  // peak_ay
              if (f[8] <= 1.797663f) {  // peak_accel_mag
                return 4;  // FHsmash
              } else {
                if (f[1] <= -449.171631f) {  // peak_gx
                  return 1;  // BHsmash
                } else {
                  if (f[1] <= 535.826202f) {  // peak_gx
                    return 4;  // FHsmash
                  } else {
                    return 4;  // FHsmash
                  }
                }
              }
            } else {
              return 1;  // BHsmash
            }
          }
        }
      } else {
        return 1;  // BHsmash
      }
    } else {
      if (f[14] <= -2.293474f) {  // ratio_gx_gy
        if (f[1] <= -660.960144f) {  // peak_gx
          if (f[13] <= 0.312500f) {  // peak_timing
            return 4;  // FHsmash
          } else {
            return 4;  // FHsmash
          }
        } else {
          return 1;  // BHsmash
        }
      } else {
        if (f[10] <= 1.012386f) {  // peak_ay
          return 1;  // BHsmash
        } else {
          return 4;  // FHsmash
        }
      }
    }
  } else {
    if (f[14] <= 2.026409f) {  // ratio_gx_gy
      return 4;  // FHsmash
    } else {
      if (f[14] <= 2.252339f) {  // ratio_gx_gy
        return 1;  // BHsmash
      } else {
        return 4;  // FHsmash
      }
    }
  }
}
}

static int tree_12(const float* f) {
if (f[2] <= 34.305510f) {  // peak_gy
  if (f[8] <= 1.057915f) {  // peak_accel_mag
    if (f[5] <= -0.109446f) {  // mean_gy
      if (f[12] <= 203905.578125f) {  // energy_gyro
        return 3;  // FHloop
      } else {
        return 3;  // FHloop
      }
    } else {
      return 3;  // FHloop
    }
  } else {
    if (f[12] <= 106219.055374f) {  // energy_gyro
      return 5;  // zzz
    } else {
      return 3;  // FHloop
    }
  }
} else {
  if (f[9] <= 0.785500f) {  // peak_ax
    if (f[7] <= 57.692949f) {  // rms_gyro
      if (f[7] <= 47.543003f) {  // rms_gyro
        return 1;  // BHsmash
      } else {
        return 0;  // BHdrive
      }
    } else {
      return 2;  // FHdrive
    }
  } else {
    if (f[3] <= 216.616241f) {  // peak_gz
      if (f[10] <= 1.228034f) {  // peak_ay
        if (f[8] <= 1.450206f) {  // peak_accel_mag
          return 1;  // BHsmash
        } else {
          if (f[8] <= 1.550661f) {  // peak_accel_mag
            return 4;  // FHsmash
          } else {
            if (f[0] <= 700.476654f) {  // peak_gyro_mag
              if (f[14] <= -2.640705f) {  // ratio_gx_gy
                if (f[3] <= 143.562294f) {  // peak_gz
                  return 4;  // FHsmash
                } else {
                  return 1;  // BHsmash
                }
              } else {
                if (f[2] <= 321.683838f) {  // peak_gy
                  if (f[11] <= 0.364987f) {  // peak_az
                    if (f[5] <= 30.409513f) {  // mean_gy
                      if (f[8] <= 2.162565f) {  // peak_accel_mag
                        return 4;  // FHsmash
                      } else {
                        return 1;  // BHsmash
                      }
                    } else {
                      return 4;  // FHsmash
                    }
                  } else {
                    if (f[2] <= 216.227310f) {  // peak_gy
                      if (f[3] <= 135.796486f) {  // peak_gz
                        return 1;  // BHsmash
                      } else {
                        return 4;  // FHsmash
                      }
                    } else {
                      return 1;  // BHsmash
                    }
                  }
                } else {
                  return 4;  // FHsmash
                }
              }
            } else {
              if (f[2] <= 279.521042f) {  // peak_gy
                if (f[11] <= 0.380648f) {  // peak_az
                  return 4;  // FHsmash
                } else {
                  if (f[12] <= 734031.062500f) {  // energy_gyro
                    return 1;  // BHsmash
                  } else {
                    return 1;  // BHsmash
                  }
                }
              } else {
                return 4;  // FHsmash
              }
            }
          }
        }
      } else {
        if (f[9] <= 2.255490f) {  // peak_ax
          return 1;  // BHsmash
        } else {
          return 4;  // FHsmash
        }
      }
    } else {
      return 4;  // FHsmash
    }
  }
}
}

static int tree_13(const float* f) {
if (f[2] <= 25.076640f) {  // peak_gy
  if (f[3] <= 15.220760f) {  // peak_gz
    if (f[3] <= -9.538407f) {  // peak_gz
      return 3;  // FHloop
    } else {
      return 5;  // zzz
    }
  } else {
    return 3;  // FHloop
  }
} else {
  if (f[0] <= 237.439415f) {  // peak_gyro_mag
    if (f[12] <= 84504.824219f) {  // energy_gyro
      if (f[6] <= 7.025331f) {  // mean_gz
        if (f[8] <= 1.049511f) {  // peak_accel_mag
          return 4;  // FHsmash
        } else {
          return 1;  // BHsmash
        }
      } else {
        return 0;  // BHdrive
      }
    } else {
      return 2;  // FHdrive
    }
  } else {
    if (f[11] <= 0.365274f) {  // peak_az
      if (f[5] <= 31.828973f) {  // mean_gy
        if (f[11] <= 0.340273f) {  // peak_az
          return 4;  // FHsmash
        } else {
          if (f[2] <= 310.185898f) {  // peak_gy
            if (f[7] <= 172.244560f) {  // rms_gyro
              return 1;  // BHsmash
            } else {
              if (f[3] <= 216.665245f) {  // peak_gz
                return 1;  // BHsmash
              } else {
                return 4;  // FHsmash
              }
            }
          } else {
            return 4;  // FHsmash
          }
        }
      } else {
        return 4;  // FHsmash
      }
    } else {
      if (f[12] <= 1392481.062500f) {  // energy_gyro
        if (f[2] <= 323.238098f) {  // peak_gy
          if (f[5] <= 13.597311f) {  // mean_gy
            if (f[11] <= 0.648123f) {  // peak_az
              if (f[7] <= 82.818340f) {  // rms_gyro
                return 1;  // BHsmash
              } else {
                return 4;  // FHsmash
              }
            } else {
              return 1;  // BHsmash
            }
          } else {
            if (f[3] <= 114.258877f) {  // peak_gz
              if (f[6] <= 18.327485f) {  // mean_gz
                if (f[11] <= 0.609317f) {  // peak_az
                  return 1;  // BHsmash
                } else {
                  if (f[8] <= 1.643361f) {  // peak_accel_mag
                    return 4;  // FHsmash
                  } else {
                    return 1;  // BHsmash
                  }
                }
              } else {
                return 4;  // FHsmash
              }
            } else {
              if (f[10] <= 1.119937f) {  // peak_ay
                if (f[3] <= 214.445885f) {  // peak_gz
                  if (f[3] <= 139.465309f) {  // peak_gz
                    if (f[1] <= -372.308411f) {  // peak_gx
                      if (f[3] <= 131.764393f) {  // peak_gz
                        return 4;  // FHsmash
                      } else {
                        return 1;  // BHsmash
                      }
                    } else {
                      return 1;  // BHsmash
                    }
                  } else {
                    return 1;  // BHsmash
                  }
                } else {
                  return 4;  // FHsmash
                }
              } else {
                return 1;  // BHsmash
              }
            }
          }
        } else {
          return 4;  // FHsmash
        }
      } else {
        if (f[3] <= 179.726929f) {  // peak_gz
          return 1;  // BHsmash
        } else {
          return 4;  // FHsmash
        }
      }
    }
  }
}
}

static int tree_14(const float* f) {
if (f[2] <= 34.305510f) {  // peak_gy
  if (f[0] <= 92.546021f) {  // peak_gyro_mag
    if (f[5] <= 0.982101f) {  // mean_gy
      return 5;  // zzz
    } else {
      return 1;  // BHsmash
    }
  } else {
    return 3;  // FHloop
  }
} else {
  if (f[11] <= 0.734609f) {  // peak_az
    if (f[1] <= -661.042084f) {  // peak_gx
      return 4;  // FHsmash
    } else {
      if (f[3] <= 216.616241f) {  // peak_gz
        if (f[8] <= 2.074123f) {  // peak_accel_mag
          if (f[8] <= 1.468114f) {  // peak_accel_mag
            if (f[9] <= 1.066515f) {  // peak_ax
              if (f[3] <= 127.097202f) {  // peak_gz
                return 1;  // BHsmash
              } else {
                return 1;  // BHsmash
              }
            } else {
              return 4;  // FHsmash
            }
          } else {
            if (f[0] <= 651.231293f) {  // peak_gyro_mag
              if (f[11] <= 0.604526f) {  // peak_az
                return 4;  // FHsmash
              } else {
                if (f[0] <= 439.187668f) {  // peak_gyro_mag
                  if (f[8] <= 1.584583f) {  // peak_accel_mag
                    if (f[2] <= 144.715645f) {  // peak_gy
                      return 4;  // FHsmash
                    } else {
                      return 1;  // BHsmash
                    }
                  } else {
                    return 1;  // BHsmash
                  }
                } else {
                  if (f[12] <= 593975.375000f) {  // energy_gyro
                    return 4;  // FHsmash
                  } else {
                    return 1;  // BHsmash
                  }
                }
              }
            } else {
              if (f[12] <= 922813.343750f) {  // energy_gyro
                if (f[1] <= 633.063751f) {  // peak_gx
                  return 1;  // BHsmash
                } else {
                  return 1;  // BHsmash
                }
              } else {
                return 4;  // FHsmash
              }
            }
          }
        } else {
          if (f[0] <= 718.273315f) {  // peak_gyro_mag
            if (f[11] <= 0.336958f) {  // peak_az
              return 4;  // FHsmash
            } else {
              if (f[11] <= 0.363533f) {  // peak_az
                if (f[4] <= 9.677709f) {  // mean_gx
                  return 1;  // BHsmash
                } else {
                  return 1;  // BHsmash
                }
              } else {
                return 1;  // BHsmash
              }
            }
          } else {
            if (f[6] <= 21.156681f) {  // mean_gz
              return 4;  // FHsmash
            } else {
              if (f[12] <= 1287995.812500f) {  // energy_gyro
                return 1;  // BHsmash
              } else {
                return 4;  // FHsmash
              }
            }
          }
        }
      } else {
        return 4;  // FHsmash
      }
    }
  } else {
    if (f[7] <= 58.700626f) {  // rms_gyro
      if (f[6] <= 6.627306f) {  // mean_gz
        return 1;  // BHsmash
      } else {
        return 0;  // BHdrive
      }
    } else {
      return 2;  // FHdrive
    }
  }
}
}

static int predict_stroke(const float* f) {
  int votes[6] = {0};
  votes[tree_0(f)]++;
  votes[tree_1(f)]++;
  votes[tree_2(f)]++;
  votes[tree_3(f)]++;
  votes[tree_4(f)]++;
  votes[tree_5(f)]++;
  votes[tree_6(f)]++;
  votes[tree_7(f)]++;
  votes[tree_8(f)]++;
  votes[tree_9(f)]++;
  votes[tree_10(f)]++;
  votes[tree_11(f)]++;
  votes[tree_12(f)]++;
  votes[tree_13(f)]++;
  votes[tree_14(f)]++;
  int best = 0;
  for (int i = 1; i < 6; i++)
    if (votes[i] > votes[best]) best = i;
  return best;
}

// Noms des classes pour le debug série
static const char* CLASS_NAMES[6] = {"BHdrive", "BHsmash", "FHdrive", "FHloop", "FHsmash", "zzz"};